import pandas as pd
import numpy as np
import json
import psycopg2
import sys
import re

from services.config import (
    DB_CONFIG
)


TARGET_DEFECTS = ["Blow Hole","Crack","Non filling","Porosity","Shrinkage","Chipoff"]

# Date range (IST). The recomended_* columns were only filled for rows created on/after
# 9 Oct 2026, so earlier rows have NULL limits and are skipped automatically.
DATE_FROM = "2026-10-09 00:00:00+05:30"
DATE_TO = None  # None = now

# Maps the raw defect names stored in part_quality to the 6 monitored categories
DEFECT_PATTERNS = [
    (r"blow\s*hole",   "Blow Hole"),
    (r"crack",         "Crack"),
    (r"non[\s_-]*filling", "Non filling"),
    (r"porosity",      "Porosity"),
    (r"shrinkage",     "Shrinkage"),
    (r"chip[\s_-]*off", "Chipoff"),
]


def safe_cn(col):
        return re.sub(r"[^a-zA-Z0-9]","_",str(col)).strip("_").replace("__","_")


def categorize_defect(defect_type):
    """Map a raw defect_type string to one of TARGET_DEFECTS, or None if not monitored."""
    if defect_type is None:
        return None
    for pattern, category in DEFECT_PATTERNS:
        if re.search(pattern, str(defect_type), flags=re.IGNORECASE):
            return category
    return None


def fetch_defective_part_parameters(conn, die, machine_id=None, date_from=DATE_FROM, date_to=DATE_TO):
    """One row per (defective part, defect record, parameter) with value + limits."""
    query = """
        SELECT
            pq.id_part,
            pq.id_die,
            pq.id_machine,
            pq.defect_type,
            pq.manufactored_on,
            op.parameter_name,
            op.value,
            op.recomended_baseline,
            op.recomended_lower_tolerance,
            op.recomended_upper_tolerance
        FROM part_quality pq
        JOIN operating_parameter op ON op.id_part = pq.id_part
        WHERE pq.id_die = %s
          AND pq.manufactored_on >= %s
          AND pq.manufactored_on <  COALESCE(%s::timestamptz, now())
    """
    params = [die, date_from, date_to]
    if machine_id:
        query += " AND pq.id_machine = %s"
        params.append(machine_id)
    query += " ORDER BY pq.manufactored_on, pq.id_part, op.parameter_name;"
    return pd.read_sql(query, conn, params=tuple(params))


def evaluate_readings(df):
    """
    Keeps readings of the 6 monitored defects that can actually be judged (value and limits
    present) and labels each one OK / BELOW / ABOVE with how far out it is.
    """
    df = df.copy()
    df["defect_category"] = df["defect_type"].apply(categorize_defect)
    df = df[df["defect_category"].notna()]

    for c in ["value", "recomended_baseline", "recomended_lower_tolerance", "recomended_upper_tolerance"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df[df["value"].notna()]
    df = df[df["recomended_lower_tolerance"].notna() & df["recomended_upper_tolerance"].notna()]
    # Limits of exactly 0 / 0 mean "no tolerance set" (as in the monitor), so skip them
    not_set = (df["recomended_lower_tolerance"] == 0) & (df["recomended_upper_tolerance"] == 0)
    df = df[~not_set].copy()

    lo, hi, val = df["recomended_lower_tolerance"], df["recomended_upper_tolerance"], df["value"]
    df["status"] = np.where(val < lo, "BELOW", np.where(val > hi, "ABOVE", "OK"))
    df["violated_limit"] = np.where(df["status"] == "BELOW", lo, np.where(df["status"] == "ABOVE", hi, np.nan))
    df["deviation"] = (val - df["violated_limit"]).abs().round(4)
    df["deviation_pct"] = np.where(
        df["violated_limit"].notna() & (df["violated_limit"] != 0),
        (df["deviation"] / df["violated_limit"].abs() * 100).round(2),
        np.nan,
    )
    df["manufactored_on"] = pd.to_datetime(df["manufactored_on"], utc=True).dt.tz_convert("Asia/Kolkata")
    return df.reset_index(drop=True)


def find_out_of_range(readings):
    """Only the readings outside the recommended limits (one row per part / parameter)."""
    out = readings[readings["status"] != "OK"]
    cols = [
        "id_part", "manufactored_on", "defect_category", "defect_type", "parameter_name",
        "value", "recomended_lower_tolerance", "recomended_upper_tolerance",
        "status", "deviation", "deviation_pct",
    ]
    return (out[cols]
            .sort_values(["manufactored_on", "id_part", "deviation_pct"], ascending=[True, True, False])
            .reset_index(drop=True))


def part_level(readings):
    """
    One row per (defective part, defect category): how many parameters were checked / out of range,
    plus a text summary and, for every parameter that went out of range, its absolute and
    percentage deviation in <parameter>_abs_dev / <parameter>_pct_dev columns (blank when in range).
    """
    r = readings.drop_duplicates(["id_part", "defect_category", "parameter_name"])
    rows = []
    for (id_part, cat), g in r.groupby(["id_part", "defect_category"], sort=False):
        bad = g[g["status"] != "OK"].sort_values("deviation_pct", ascending=False)
        row = {
            "id_part": id_part,
            "manufactored_on": g["manufactored_on"].min(),
            "defect_category": cat,
            "params_checked": len(g),
            "params_out_of_range": len(bad),
            "out_of_range_params": ", ".join(sorted(bad["parameter_name"])),
            "out_of_range_details": "; ".join(
                f"{b.parameter_name} {b.status} by {b.deviation:g}"
                + (f" ({b.deviation_pct:g}%)" if pd.notna(b.deviation_pct) else "")
                for b in bad.itertuples()
            ),
        }
        for b in bad.itertuples():
            row[f"{b.parameter_name}_abs_dev"] = b.deviation
            row[f"{b.parameter_name}_pct_dev"] = b.deviation_pct
        rows.append(row)

    df = pd.DataFrame(rows)
    # Keep the fixed columns first, then the per-parameter deviation columns as abs/pct pairs
    fixed = ["id_part", "manufactored_on", "defect_category", "params_checked",
             "params_out_of_range", "out_of_range_params", "out_of_range_details"]
    dev_params = sorted({c.rsplit("_", 2)[0] for c in df.columns if c.endswith(("_abs_dev", "_pct_dev"))})
    dev_cols = [c for p in dev_params for c in (f"{p}_abs_dev", f"{p}_pct_dev")]
    return df.reindex(columns=fixed + dev_cols)


def _stats_row(n_out):
    n = len(n_out)
    return {
        "defective_parts": n,
        "avg_params_out": round(n_out.mean(), 2),
        "median_params_out": float(n_out.median()),
        "max_params_out": int(n_out.max()),
        "pct_with_0_out": round((n_out == 0).mean() * 100, 1),
        "pct_with_1+_out": round((n_out >= 1).mean() * 100, 1),
        "pct_with_2+_out": round((n_out >= 2).mean() * 100, 1),
        "pct_with_3+_out": round((n_out >= 3).mean() * 100, 1),
    }


def analysis_tables(readings, parts):
    cats = [c for c in TARGET_DEFECTS if c in set(parts["defect_category"])]

    # Each part counted once for the ALL rows (a part can carry more than one defect category)
    all_parts = (readings.drop_duplicates(["id_part", "parameter_name"])
                         .groupby("id_part")["status"].apply(lambda s: (s != "OK").sum()))

    # Table 1: how many parameters are out of range when a defect occurs
    t1 = {c: _stats_row(parts.loc[parts["defect_category"] == c, "params_out_of_range"]) for c in cats}
    t1["ALL"] = _stats_row(all_parts)
    t1 = pd.DataFrame(t1).T
    t1[["defective_parts", "max_params_out"]] = t1[["defective_parts", "max_params_out"]].astype(int)
    t1.index.name = "defect"

    # Table 2: distribution - number of defective parts by count of out-of-range parameters
    def bucket(s):
        return s.clip(upper=4).map(lambda x: "4+" if x >= 4 else str(int(x)))
    order = ["0", "1", "2", "3", "4+"]
    t2 = pd.crosstab(parts["defect_category"], bucket(parts["params_out_of_range"])).reindex(columns=order, fill_value=0)
    t2 = t2.reindex(cats)
    t2.loc["ALL"] = pd.crosstab(index=["ALL"] * len(all_parts), columns=bucket(all_parts)).reindex(columns=order, fill_value=0).iloc[0]
    t2.columns = [f"{c} param(s) out" for c in t2.columns]
    t2.index.name = "defect"

    # Table 3: parameter x defect - parts where that parameter was out of range
    r = readings.drop_duplicates(["id_part", "defect_category", "parameter_name"])
    bad = r[r["status"] != "OK"]
    denom = parts.groupby("defect_category")["id_part"].nunique()
    denom_all = parts["id_part"].nunique()
    if bad.empty:
        return t1, t2, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    counts = (bad.pivot_table(index="parameter_name", columns="defect_category",
                              values="id_part", aggfunc="nunique", fill_value=0)
                 .reindex(columns=cats, fill_value=0))
    counts["ALL"] = bad.groupby("parameter_name")["id_part"].nunique()
    counts = counts.sort_values("ALL", ascending=False)

    pct = counts.copy().astype(float)
    for c in cats:
        pct[c] = (counts[c] / denom[c] * 100).round(1)
    pct["ALL"] = (counts["ALL"] / denom_all * 100).round(1)

    display = counts.astype(int).astype(str) + " (" + pct.round(0).astype(int).astype(str) + "%)"
    counts.index.name = pct.index.name = display.index.name = "parameter"
    counts.columns.name = pct.columns.name = display.columns.name = None
    return t1, t2, counts, pct, display


def main(machine_id, die):
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        df_all = fetch_defective_part_parameters(conn, die, machine_id)
    finally:
        conn.close()

    readings = evaluate_readings(df_all) if not df_all.empty else df_all
    if readings.empty:
        print(f"No judgeable readings for defective parts on die {die} in this date range "
              f"(no data, or recommended limits not set).")
        return

    tag = safe_cn(die)
    out = find_out_of_range(readings)
    parts = part_level(readings)
    t1, t2, counts, pct, display = analysis_tables(readings, parts)

    # Detailed data goes to CSV only
    out.to_csv(f"out_of_range_readings_{tag}.csv", index=False)
    parts.to_csv(f"defective_parts_param_counts_{tag}.csv", index=False)
    t1.to_csv(f"analysis_params_out_per_defect_{tag}.csv")
    t2.to_csv(f"analysis_distribution_{tag}.csv")
    if not counts.empty:
        counts.to_csv(f"analysis_param_by_defect_counts_{tag}.csv")
        pct.to_csv(f"analysis_param_by_defect_pct_{tag}.csv")

    n_parts = parts["id_part"].nunique()
    n_zero = (parts.groupby("id_part")["params_out_of_range"].sum() == 0).sum()
    print(f"Die {die}: {n_parts} defective parts analysed ({len(out)} out-of-range readings)")
    print(f"{n_zero} of them ({n_zero / n_parts * 100:.1f}%) had no parameter out of range\n")

    print("1) Parameters out of range per defective part")
    print(t1.to_string(), "\n")

    print("2) Number of defective parts by count of out-of-range parameters")
    print(t2.to_string(), "\n")

    if not display.empty:
        print("3) Parts with each parameter out of range, by defect  [count (% of that defect's parts)]")
        print(display.to_string(), "\n")

    print(f"CSV files saved (…_{tag}.csv): out_of_range_readings, defective_parts_param_counts, "
          f"analysis_params_out_per_defect, analysis_distribution, analysis_param_by_defect_counts/pct")


if __name__ == "__main__":
    # usage: python parameter_analysis.py <die> [machine_id]
    die_arg = sys.argv[1]
    machine_arg = "UBE 850T-2"
    main(machine_arg, die_arg)