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
GOOD_LABEL = "Non-defective"

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


def fetch_good_part_parameters(conn, die, machine_id=None, date_from=DATE_FROM, date_to=DATE_TO):
    """
    One row per (non-defective part, parameter). A part is non-defective when it has no
    part_quality row other than PLC communication entries.
    """
    query = r"""
        SELECT
            p.id_part,
            p.id_die,
            p.id_machine,
            NULL::text AS defect_type,
            p.manufactored_on,
            op.parameter_name,
            op.value,
            op.recomended_baseline,
            op.recomended_lower_tolerance,
            op.recomended_upper_tolerance
        FROM part p
        JOIN operating_parameter op ON op.id_part = p.id_part
        WHERE p.id_die = %s
          AND p.manufactored_on >= %s
          AND p.manufactored_on <  COALESCE(%s::timestamptz, now())
          AND NOT EXISTS (
              SELECT 1 FROM part_quality pq
              WHERE pq.id_part = p.id_part
                AND (pq.defect_type LIKE 'PLC\_COMM%%') IS NOT TRUE
          )
    """
    params = [die, date_from, date_to]
    if machine_id:
        query += " AND p.id_machine = %s"
        params.append(machine_id)
    query += " ORDER BY p.manufactored_on, p.id_part, op.parameter_name;"
    return pd.read_sql(query, conn, params=tuple(params))


def evaluate_readings(df, defective=True):
    """
    Keeps readings that can actually be judged (value and limits present) and labels each one
    OK / BELOW / ABOVE with how far out it is. For defective parts only the 6 monitored defect
    categories are kept; non-defective parts all get the GOOD_LABEL category.
    """
    df = df.copy()
    if defective:
        df["defect_category"] = df["defect_type"].apply(categorize_defect)
        df = df[df["defect_category"].notna()]
    else:
        df["defect_category"] = GOOD_LABEL

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
    One row per (part, category): how many parameters were checked / out of range, plus a text
    summary and, for every parameter that went out of range, its absolute and percentage
    deviation in <parameter>_abs_dev / <parameter>_pct_dev columns (blank when in range).
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
        "parts": n,
        "avg_params_out": round(n_out.mean(), 2),
        "median_params_out": float(n_out.median()),
        "max_params_out": int(n_out.max()),
        "pct_with_0_out": round((n_out == 0).mean() * 100, 1),
        "pct_with_1+_out": round((n_out >= 1).mean() * 100, 1),
        "pct_with_2+_out": round((n_out >= 2).mean() * 100, 1),
        "pct_with_3+_out": round((n_out >= 3).mean() * 100, 1),
    }


def analysis_tables(readings, parts):
    present = set(parts["defect_category"])
    cats = [c for c in TARGET_DEFECTS if c in present] + [c for c in sorted(present) if c not in TARGET_DEFECTS]

    # Each part counted once for the ALL rows (a part can carry more than one defect category)
    all_parts = (readings.drop_duplicates(["id_part", "parameter_name"])
                         .groupby("id_part")["status"].apply(lambda s: (s != "OK").sum()))

    # Table 1: how many parameters are out of range per part
    t1 = {c: _stats_row(parts.loc[parts["defect_category"] == c, "params_out_of_range"]) for c in cats}
    t1["ALL"] = _stats_row(all_parts)
    t1 = pd.DataFrame(t1).T
    t1[["parts", "max_params_out"]] = t1[["parts", "max_params_out"]].astype(int)
    t1.index.name = "group"

    # Table 2: distribution - number of parts by count of out-of-range parameters
    def bucket(s):
        return s.clip(upper=4).map(lambda x: "4+" if x >= 4 else str(int(x)))
    order = ["0", "1", "2", "3", "4+"]
    t2 = pd.crosstab(parts["defect_category"], bucket(parts["params_out_of_range"])).reindex(columns=order, fill_value=0)
    t2 = t2.reindex(cats)
    t2.loc["ALL"] = pd.crosstab(index=["ALL"] * len(all_parts), columns=bucket(all_parts)).reindex(columns=order, fill_value=0).iloc[0]
    t2.columns = [f"{c} param(s) out" for c in t2.columns]
    t2.index.name = "group"
    if len(cats) == 1:  # ALL would just repeat the single row
        t1, t2 = t1.drop("ALL"), t2.drop("ALL")

    # Table 3: parameter x category - parts where that parameter was out of range
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


def run_analysis(readings, label, tag, suffix, parts_stem):
    """Builds, saves (CSV) and prints the analysis tables for one group of parts."""
    if readings.empty:
        print(f"[{label}] No judgeable readings in this date range (no data, or limits not set).\n")
        return None

    out = find_out_of_range(readings)
    parts = part_level(readings)
    t1, t2, counts, pct, display = analysis_tables(readings, parts)

    # Detailed data goes to CSV only
    out.to_csv(f"out_of_range_readings_{tag}{suffix}.csv", index=False)
    parts.to_csv(f"{parts_stem}_{tag}.csv", index=False)
    t1.to_csv(f"analysis_params_out_per_defect_{tag}{suffix}.csv")
    t2.to_csv(f"analysis_distribution_{tag}{suffix}.csv")
    if not counts.empty:
        counts.to_csv(f"analysis_param_by_defect_counts_{tag}{suffix}.csv")
        pct.to_csv(f"analysis_param_by_defect_pct_{tag}{suffix}.csv")

    per_part = (readings.drop_duplicates(["id_part", "parameter_name"])
                        .groupby("id_part")["status"].apply(lambda s: (s != "OK").sum()))
    n_parts = len(per_part)
    n_zero = int((per_part == 0).sum())

    print("=" * 78)
    print(f"{label.upper()}: {n_parts} parts analysed ({len(out)} out-of-range readings)")
    print(f"{n_zero} of them ({n_zero / n_parts * 100:.1f}%) had no parameter out of range")
    print("=" * 78 + "\n")

    print("1) Parameters out of range per part")
    print(t1.to_string(), "\n")

    print("2) Number of parts by count of out-of-range parameters")
    print(t2.to_string(), "\n")

    if not display.empty:
        print("3) Parts with each parameter out of range  [count (% of parts in that group)]")
        print(display.to_string(), "\n")

    return {
        "n_parts": n_parts,
        "avg_out": per_part.mean(),
        "pct_zero": n_zero / n_parts * 100,
        "pct_by_param": pct["ALL"] if not pct.empty else pd.Series(dtype=float),
    }


def comparison_table(res_def, res_good):
    """Per parameter: % of defective vs non-defective parts that had it out of range."""
    cmp = pd.DataFrame({
        "pct_defective_parts_out": res_def["pct_by_param"],
        "pct_nondefective_parts_out": res_good["pct_by_param"],
    }).fillna(0.0)
    cmp["difference_pp"] = (cmp["pct_defective_parts_out"] - cmp["pct_nondefective_parts_out"]).round(1)
    cmp["ratio"] = np.where(
        cmp["pct_nondefective_parts_out"] > 0,
        (cmp["pct_defective_parts_out"] / cmp["pct_nondefective_parts_out"]).round(2),
        np.nan,
    )
    cmp.index.name = "parameter"
    return cmp.sort_values("difference_pp", ascending=False)


def main(machine_id, die):
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        df_def = fetch_defective_part_parameters(conn, die, machine_id)
        df_good = fetch_good_part_parameters(conn, die, machine_id)
    finally:
        conn.close()

    tag = safe_cn(die)
    print(f"Die {die}\n")

    readings_def = evaluate_readings(df_def, defective=True) if not df_def.empty else df_def
    readings_good = evaluate_readings(df_good, defective=False) if not df_good.empty else df_good

    res_def = run_analysis(readings_def, "Defective parts", tag, "", "defective_parts_param_counts")
    res_good = run_analysis(readings_good, "Non-defective parts", tag, "_nondefective", "nondefective_parts_param_counts")

    if res_def and res_good:
        print("=" * 78)
        print("DEFECTIVE vs NON-DEFECTIVE")
        print("=" * 78)
        summary = pd.DataFrame({
            "parts": [res_def["n_parts"], res_good["n_parts"]],
            "avg_params_out_per_part": [round(res_def["avg_out"], 2), round(res_good["avg_out"], 2)],
            "pct_parts_with_0_out": [round(res_def["pct_zero"], 1), round(res_good["pct_zero"], 1)],
        }, index=["Defective", "Non-defective"])
        print(summary.to_string(), "\n")

        cmp = comparison_table(res_def, res_good)
        print("4) % of parts with each parameter out of range (sorted by gap)")
        print(cmp.to_string(), "\n")
        cmp.to_csv(f"comparison_defective_vs_nondefective_{tag}.csv")
        summary.to_csv(f"comparison_summary_{tag}.csv")

    print(f"CSV files saved in the current folder (…_{tag}…csv).")


if __name__ == "__main__":
    # usage: python parameter_analysis.py <die> [machine_id]
    die_arg = sys.argv[1]
    machine_arg = "UBE 850T-2"
    main(machine_arg, die_arg)