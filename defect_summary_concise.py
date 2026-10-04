"""
Concise per-die defect / part summary.

- One bullet per recorded defect type (real defects, fully expanded).
- Infrastructure/system events are named individually where they form a
  distinct type (packet timeouts, SLMP START_ACK, connect timeout, recovery
  markers); only the timestamp-variant "circuit open until..." rows are kept
  generalized as a single bullet.
"""
import os
import pandas as pd
import psycopg2

from services.config import DB_CONFIG

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "defect_summary_concise.md")

CIRCUIT_GROUP = "PLC_COMMUNICATION_FAILED_PLC circuit open until ..."


def classify(row_type):
    t = str(row_type)
    if t.upper().startswith("PLC_COMMUNICATION_FAILED"):
        if "circuit open until" in t:
            return "plc_circuit"
        return "plc_named"
    if t.upper() == "RECOVERY_PENDING_AFTER_BACKEND_RESTART":
        return "recovery"
    return "real"


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    defects = pd.read_sql(
        "SELECT id_die, defect_type FROM part_quality "
        "WHERE defect_type IS NOT NULL ORDER BY id_die, defect_type", conn)
    parts = pd.read_sql(
        """
        SELECT p.id_die,
               count(*)                                       AS n_parts,
               count(DISTINCT p.id_machine)                   AS n_machines,
               min(p.manufactored_on)                         AS first_data,
               max(p.manufactored_on)                         AS last_data
        FROM part p
        GROUP BY p.id_die ORDER BY p.id_die
        """, conn)
    conn.close()

    defects = defects.assign(kind=defects["defect_type"].map(classify))
    real = defects[defects["kind"] == "real"]
    infra = defects[defects["kind"] != "real"]

    def infra_bullets(d_infra):
        bullets = []
        named = d_infra[d_infra["kind"].isin(["plc_named", "recovery"])]
        for t, n in named["defect_type"].value_counts().sort_values(ascending=False).items():
            bullets.append(f"- {t}: {int(n)}")
        circ = d_infra[d_infra["kind"] == "plc_circuit"]
        if len(circ):
            n_variants = int(circ["defect_type"].nunique())
            bullets.append(
                f"- {CIRCUIT_GROUP}: {len(circ)} rows "
                f"({n_variants} distinct timestamps)")
        return bullets

    md = []
    md.append(f"_Generated from rico DB ({pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')})._")
    md.append("")

    for die in parts["id_die"]:
        d_real = real[real["id_die"] == die]
        d_infra = infra[infra["id_die"] == die]
        md.append(f"# {die}")
        md.append("")
        md.append(f"Total defects recorded: **{int(len(defects[defects['id_die'] == die]))}**")
        md.append("")
        counts = d_real["defect_type"].value_counts().sort_values(ascending=False)
        for t, n in counts.items():
            md.append(f"- {t}: {int(n)}")
        ib = infra_bullets(d_infra)
        if ib:
            md.append("")
            md.append("Infrastructure / system events:")
            md.append("")
            md.extend(ib)
        md.append("")

    md.append("# Overall Part Data")
    md.append("")
    md.append("| Die | Total Parts | Machines | First Available Data | Last Available Data |")
    md.append("|---|---|--:|---|---|---|")
    for _, r in parts.iterrows():
        md.append(f"| {r['id_die']} | {int(r['n_parts'])} | {int(r['n_machines'])} "
                  f"| {pd.Timestamp(r['first_data']).date()} | {pd.Timestamp(r['last_data']).date()} |")
    md.append("| Total | " + str(int(parts["n_parts"].sum())) + " | — | — | — |")
    md.append("")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("Saved:", OUT)


if __name__ == "__main__":
    main()