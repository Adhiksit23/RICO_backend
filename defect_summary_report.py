"""
Defect / part summary report across all dies.

Sections:
  1. Recorded defects per die (total + per defect type).
  2. Parts per die with first / last manufactured and first / last recorded.

Outputs:
  defect_summary_report.md
  defect_summary_by_die.csv       one row per die
  defect_types_by_die.csv         long format (die, defect_type, count)
"""
import os
import pandas as pd
import psycopg2

from services.config import DB_CONFIG

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_MD = os.path.join(ROOT, "defect_summary_report.md")
OUT_DIE = os.path.join(ROOT, "defect_summary_by_die.csv")
OUT_TYPES = os.path.join(ROOT, "defect_types_by_die.csv")


def main():
    conn = psycopg2.connect(**DB_CONFIG)

    dies = pd.read_sql(
        "SELECT id_die, id_machine, id_client, enabled, description "
        "FROM die ORDER BY id_die", conn)

    parts = pd.read_sql(
        """
        SELECT p.id_die,
               count(*)                                                            AS n_parts,
               min(p.manufactored_on)                                              AS first_made,
               max(p.manufactored_on)                                              AS last_made,
               min(p.created_at)                                                   AS first_recorded,
               max(p.created_at)                                                   AS last_recorded
        FROM part p
        GROUP BY p.id_die
        ORDER BY p.id_die
        """, conn)

    quality_total = pd.read_sql(
        """
        SELECT id_die, count(*) AS n_defects,
               count(DISTINCT defect_type) AS n_distinct_types
        FROM part_quality
        WHERE defect_type IS NOT NULL
        GROUP BY id_die ORDER BY id_die
        """, conn)

    types = pd.read_sql(
        """
        SELECT id_die, defect_type, count(*) AS n
        FROM part_quality
        WHERE defect_type IS NOT NULL
        GROUP BY id_die, defect_type
        ORDER BY id_die, n DESC
        """, conn)

    conn.close()

    summary = dies[["id_die", "id_machine"]].merge(
        parts, on="id_die", how="outer").merge(
        quality_total, on="id_die", how="outer")
    summary["n_parts"] = summary["n_parts"].fillna(0).astype(int)
    summary["n_defects"] = summary["n_defects"].fillna(0).astype(int)
    summary["n_distinct_types"] = summary["n_distinct_types"].fillna(0).astype(int)

    summary.to_csv(OUT_DIE, index=False)
    types.to_csv(OUT_TYPES, index=False)

    # Group every PLC-communication-failure variant into one row for readability.
    # The full (un-grouped) per-type detail is kept in defect_types_by_die.csv.
    types_g = types.copy()
    is_plc = types_g["defect_type"].str.upper().str.startswith("PLC_COMMUNICATION_FAILED")
    types_g.loc[is_plc, "defect_type"] = "PLC_COMMUNICATION_FAILED_*"
    n_plc_variants = int(is_plc.sum())
    types_g = types_g.groupby(["id_die", "defect_type"], as_index=False)["n"].sum()

    pivot = types_g.pivot(index="defect_type", columns="id_die", values="n").fillna(0)
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("Total", ascending=False)
    pivot = pivot.astype(int)
    order = list(dies["id_die"]) + ["Total"]
    pivot = pivot.reindex(columns=[c for c in order if c in pivot.columns])

    md = []
    md.append("# Defect & Part Summary — All Dies (as of " +
              pd.Timestamp.now().strftime("%Y-%m-%d %H:%M") + ")")
    md.append("")
    md.append(f"- Dies: **{', '.join(dies['id_die'])}**")
    md.append(f"- Total parts recorded: **{int(summary['n_parts'].sum())}**")
    md.append(f"- Total defects recorded: **{int(summary['n_defects'].sum())}**")
    md.append(f"- Distinct defect types (raw): **{types['defect_type'].nunique()}** "
              f"(of which **{n_plc_variants}** are PLC-communication-failure variants, "
              "grouped as `PLC_COMMUNICATION_FAILED_*` below)")
    md.append("")

    md.append("## 1) Recorded defects per die")
    md.append("")
    md.append("### 1a) Totals per die")
    md.append("")
    md.append("| Die | Machine | Parts | Defects | Distinct defect types |")
    md.append("|---|------|--:|--:|--:|")
    for _, r in summary.iterrows():
        md.append(f"| {r['id_die']} | {r['id_machine']} | {r['n_parts']} | "
                  f"{r['n_defects']} | {r['n_distinct_types']} |")
    md.append("")

    md.append("### 1b) Defect counts by type per die")
    md.append("")
    md.append("_`PLC_COMMUNICATION_FAILED_*` groups all PLC-communication-failure variants; "
              "the full variant list is in `defect_types_by_die.csv`._")
    md.append("")
    md.append("| Defect type | " + " | ".join(dies["id_die"]) + " | Total |")
    md.append("|---|" + "---|" * len(dies) + "|---|")
    for dt, row in pivot.iterrows():
        md.append(f"| {dt} | " + " | ".join(str(int(row[d])) for d in dies["id_die"]) +
                  f" | {int(row['Total'])} |")
    md.append("")

    md.append("### 1c) Breakdown per die")
    md.append("")
    for d in dies["id_die"]:
        sub = types_g[types_g["id_die"] == d].sort_values("n", ascending=False)
        n_qual = int(summary.loc[summary["id_die"] == d, "n_defects"].iloc[0]) if len(summary) else 0
        n_raw = int(types[types["id_die"] == d]["defect_type"].nunique())
        md.append(f"#### Die {d} — {n_qual} defects ({len(sub)} grouped types "
                  f"[{n_raw} raw, PLC-comm variants grouped])")
        md.append("")
        md.append("| Defect type | Count |")
        md.append("|---|---|--:|")
        for _, r in sub.iterrows():
            md.append(f"| {r['defect_type']} | {int(r['n'])} |")
        md.append("")

    md.append("## 2) Parts per die — first & last made / recorded")
    md.append("")
    md.append("| Die | Parts | First made | Last made | First recorded | Last recorded |")
    md.append("|---|--:|---|---|---|---|")
    for _, r in summary.iterrows():
        fm = str(r["first_made"]) if pd.notna(r["first_made"]) else "-"
        lm = str(r["last_made"]) if pd.notna(r["last_made"]) else "-"
        fr = str(r["first_recorded"]) if pd.notna(r["first_recorded"]) else "-"
        lr = str(r["last_recorded"]) if pd.notna(r["last_recorded"]) else "-"
        md.append(f"| {r['id_die']} | {r['n_parts']} | {fm} | {lm} | {fr} | {lr} |")
    md.append("")

    md.append("---")
    md.append("_Generated by `defect_summary_report.py` from `rico.die` / `rico.part` / "
              "`rico.part_quality`._")
    md.append("")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print("== Defects per die ==")
    print(summary.to_string(index=False))
    print("\n== Defect type x die matrix ==")
    print(pivot.to_string())
    print("\nSaved:", OUT_MD, "|", OUT_DIE, "|", OUT_TYPES)


if __name__ == "__main__":
    main()