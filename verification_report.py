"""
S14 verification against the latest trained models.

Two scopes:
  defective: every defective part recorded in rico.part_quality for die S14.
  all      : every part of die S14 (good + defective), with actual defects joined in.

For each part:
  - pull its operating_parameter rows,
  - rebuild the same _inrange/_pctdev features used in training,
  - run the newest per-defect voting model (threshold from the pkl, 0.40).

Outputs per scope:
  - a CSV with the base table columns plus new columns:
        defect_prediction_done  -> 1 if a prediction could be computed for the part, else 0
        accuracy                -> part-level correctness:
                                    - defective, mappable defect: 1.0 if the model caught it, else 0.0
                                    - good part (no defect):       1.0 if no defect was flagged, else 0.0
                                    - defect not mappable:         blank
  - a report on false negatives and accuracy.
"""
import os, re, glob, pickle, sys
import pandas as pd
import numpy as np
import psycopg2

from services.config import DB_CONFIG
from services.predictor import PARAM_MAP_BL, TARGET_DEFECTS, latest_model_path

ROOT = os.path.dirname(os.path.abspath(__file__))
DIE = "S14"

OUT = {
    "defective": ("S14_part_quality_predictions.csv", "S14_defect_prediction_report.md"),
    "all":       ("S14_all_parts_predictions.csv",    "S14_all_parts_prediction_report.md"),
}

# part_quality columns that make up "the actual defects"
DEFECT_IFACE = ["updated_at", "category", "zone", "sub_zone", "view", "defect_type"]
# defective-scope base = the whole part_quality table
PART_QUALITY_COLS = ["id_part", "id_die"] + DEFECT_IFACE + ["id_machine"]
# all-scope base = part table + the actual-defect block (id_part shared, id_machine from part)
PART_COLS = ["id_part", "id_die", "id_client", "id_machine", "manufactored_on", "created_at"]
ACTUAL_COLS = ["updated_at", "category", "zone", "sub_zone", "view", "defect_type"]


def safe_cn(col):
    return re.sub(r"[^a-zA-Z0-9]", "_", str(col)).strip("_").replace("__", "_")


def normalize(name):
    return re.sub(r"[^a-zA-Z0-9]", "", str(name)).lower()


def match_target_defect(name):
    n = normalize(name)
    for tag in TARGET_DEFECTS:
        if normalize(tag) in n:
            return tag
    return None


def load_latest_models():
    models = {}
    for tag in TARGET_DEFECTS:
        path = latest_model_path(DIE, tag)
        if path is None:
            print(f"  ! no model for {tag}")
            continue
        models[tag] = pickle.load(open(path, "rb"))
        print(f"  loaded {os.path.basename(path)}")
    return models


def get_baselines(conn):
    query = """
        SELECT parameter_name, baseline, upper_tolerance, lower_tolerance
        FROM calibration_parameter c
        WHERE c.id_die = %s
        AND c.id_calibration = (
          SELECT MAX(id_calibration)
          FROM calibration_parameter
          WHERE id_die = %s
        )
    """
    df = pd.read_sql(query, conn, params=(DIE, DIE))
    return {
        r["parameter_name"]: (r["baseline"], r["lower_tolerance"], r["upper_tolerance"])
        for _, r in df.iterrows()
    }


def build_features(op_rows, baselines):
    if op_rows is None or op_rows.empty:
        return None
    df = op_rows.pivot_table(index=["id_part"], columns="parameter_name", values="value",
                             aggfunc="first")
    feat_rows = []
    for idx, row in df.iterrows():
        feats = {}
        for col, (avg, min_r, max_r) in baselines.items():
            # baseline key = mapped parameter name (= column name in the pivoted
            # operating_parameter table); the raw API name is only used for the
            # feature column label, mirroring model_trainer.py
            val = pd.to_numeric(row.get(col, np.nan), errors="coerce")
            col_raw = PARAM_MAP_BL[col]
            cn = safe_cn(col_raw)
            if pd.isna(val):
                feats[f"{cn}_inrange"] = 0
                feats[f"{cn}_pctdev"] = 0.0
            else:
                feats[f"{cn}_inrange"] = int(min_r <= val <= max_r)
                pct = (val - avg) / avg if avg != 0 else 0.0
                feats[f"{cn}_pctdev"] = float(np.clip(pct, -0.30, 0.30))
        feat_rows.append(feats)
    return pd.DataFrame(feat_rows, index=df.index)


def predict_probability(feat_df, model):
    df_input = feat_df[model["scaler"].feature_names_in_]
    X_scaled = model["scaler"].transform(df_input)
    X_pca = model["pca"].transform(X_scaled)
    X_cca = model["cca"].transform(X_pca)
    prob = model["model"].predict_proba(X_cca)[:, 1]
    return pd.Series(prob, index=feat_df.index)


def run(scope):
    csv_name, report_name = OUT[scope]
    out_csv = os.path.join(ROOT, csv_name)
    out_report = os.path.join(ROOT, report_name)

    conn = psycopg2.connect(**DB_CONFIG)
    print(f"== [{scope}] Loading latest S14 models ==")
    models = load_latest_models()

    if scope == "defective":
        print("== Pulling defective parts for S14 from part_quality ==")
        base = pd.read_sql(
            f"SELECT {', '.join(PART_QUALITY_COLS)} FROM part_quality "
            f"WHERE id_die = %s ORDER BY id_part",
            conn, params=(DIE,))
        print(f"  defective parts: {len(base)}")
    else:
        print("== Pulling all S14 parts and joining actual defects ==")
        base = pd.read_sql(
            f"""
            SELECT p.{', p.'.join(PART_COLS)}, pq.{', pq.'.join(ACTUAL_COLS)}
            FROM part p
            LEFT JOIN part_quality pq ON pq.id_part = p.id_part
            WHERE p.id_die = %s
            ORDER BY p.id_part
            """, conn, params=(DIE,))
        print(f"  all parts: {len(base)} (defective: {base['defect_type'].notna().sum()})")

    part_ids = list(base["id_part"].astype(str))
    op_rows = pd.read_sql(
        "SELECT id_part, parameter_name, value FROM operating_parameter WHERE id_part = ANY(%s)",
        conn, params=(part_ids,))
    print(f"  operating_parameter rows: {len(op_rows)} for {op_rows['id_part'].nunique()} parts")

    print("== Loading latest S14 calibration baselines ==")
    baselines = get_baselines(conn)
    print(f"  {len(baselines)} baselines")

    try:
        feat_df = build_features(op_rows, baselines)
    finally:
        conn.close()
    predicted_parts = set(feat_df.index.astype(str)) if feat_df is not None else set()
    print(f"  parts with parameters (predictable): {len(predicted_parts)}")

    probs = pd.DataFrame(index=base["id_part"].astype(str))
    preds = pd.DataFrame(index=base["id_part"].astype(str))
    for tag, model in models.items():
        if feat_df is None or feat_df.empty:
            p = pd.Series(np.nan, index=probs.index)
        else:
            p = predict_probability(feat_df, model).reindex(probs.index).astype(float)
        probs[f"prob_{tag}"] = p.values
        t = model.get("threshold", 0.40)
        preds[f"pred_{tag}"] = (p.fillna(0.0) >= t).astype(int)

    base = base.join(probs, on="id_part").join(preds, on="id_part")
    base["defect_prediction_done"] = base["id_part"].map(
        lambda pid: 1 if pid in predicted_parts else 0)
    base["mapped_defect"] = base["defect_type"].map(match_target_defect)

    def accuracy_of(row):
        if row["id_part"] not in predicted_parts:
            return np.nan
        mapped = row["mapped_defect"]
        if pd.notna(mapped) and isinstance(mapped, str):
            # defective part: accurate only if the actual defect was predicted
            return float(int(row[f"pred_{mapped}"]))
        if pd.isna(row["defect_type"]):
            # good part: accurate only if nothing was flagged
            return float(int(sum(row[f"pred_{t}"] for t in TARGET_DEFECTS) == 0))
        return np.nan  # defective but unmappable defect name

    base["accuracy"] = base.apply(accuracy_of, axis=1)

    extra = ["mapped_defect"] + \
        [f"prob_{t}" for t in TARGET_DEFECTS] + \
        [f"pred_{t}" for t in TARGET_DEFECTS] + \
        ["defect_prediction_done", "accuracy"]
    if scope == "defective":
        csv_cols = PART_QUALITY_COLS + extra
    else:
        csv_cols = PART_COLS + ACTUAL_COLS + extra
    base.to_csv(out_csv, index=False, columns=csv_cols)
    print(f"\nCSV saved: {out_csv} ({len(base)} rows)")

    writer = write_report_defective if scope == "defective" else write_report_all
    writer(base, out_report)
    print(f"Report saved: {out_report}")


def model_date(tag):
    matches = glob.glob(os.path.join(ROOT, "models", DIE, f"{DIE}_{tag}_*_voting.pkl"))
    dates = []
    for path in matches:
        m = re.search(r"_(\d{8})_voting\.pkl$", os.path.basename(path))
        if m:
            dates.append(m.group(1))
    return max(dates) if dates else "?"


def _headers(lines):
    add = lines.append
    add("# S14 Defect-Prediction Report — False Negatives & Accuracy")
    add("")
    add(f"- Die: **{DIE}**  |  Defect models: latest per defect " +
        ", ".join(f"`{t}` `{model_date(t)}`" for t in TARGET_DEFECTS))
    add("- Prediction threshold: **0.40** (same as training)")
    add("")


def _save(lines, out_report):
    with open(out_report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_report_defective(quality, out_report):
    lines = []
    add = lines.append
    _headers(lines)
    add(f"- Scope: defective parts in `rico.part_quality` (die {DIE}): **{len(quality)}**")
    n_computed = int(quality["defect_prediction_done"].sum())
    add(f"- Parts with operating parameters (prediction computed): **{n_computed}** "
        f"({len(quality) - n_computed} lack operating_parameter rows)")
    mapped = quality.dropna(subset=["mapped_defect"])
    n_na = int(quality["mapped_defect"].isna().sum())
    add(f"- Defects mappable to a target model: **{len(mapped)}** "
        f"(unmapped/unsupported defect names: **{n_na}**)")
    add("")
    add("## Overall")
    add("")
    overall_caught = int(mapped["accuracy"].sum())
    overall_fn = len(mapped) - overall_caught
    overall_acc = (overall_caught / len(mapped)) if len(mapped) else 0.0
    overall_fn_rate = (overall_fn / len(mapped)) if len(mapped) else 0.0
    add(f"- Accuracy (actual defect caught): **{overall_acc*100:.2f}%** "
        f"({overall_caught}/{len(mapped)})")
    add(f"- **False negatives: {overall_fn}** ({overall_fn_rate*100:.2f}% of mapped defects)")
    add("")
    add("## Per-defect breakdown")
    add("")
    add("| Defect | Defective parts | Caught | False negatives | Recall (accuracy) | False-negative rate |")
    add("|---|---|--:|--:|--:|--:|")
    for tag in TARGET_DEFECTS:
        sub = mapped[mapped["mapped_defect"] == tag]
        total = int(sub.shape[0])
        if total == 0:
            add(f"| {tag} | 0 | - | - | - | - |")
            continue
        caught = int(sub["accuracy"].sum())
        fn = total - caught
        add(f"| {tag} | {total} | {caught} | **{fn}** | {caught/total*100:.2f}% | {fn/total*100:.2f}% |")
    add("")
    add("## False-negative part IDs (actual defect not predicted)")
    add("")
    fns = mapped[mapped["accuracy"] == 0.0]
    if fns.empty:
        add("None — every mappable defect was caught.")
    else:
        for tag in TARGET_DEFECTS:
            sub = fns[fns["mapped_defect"] == tag]
            if sub.empty:
                continue
            add(f"### {tag} — {len(sub)} false negative{'s' if len(sub) != 1 else ''}")
            add("")
            add("| id_part | actual defect_type | probability assigned to actual defect |")
            add("|---|---|--:|")
            for _, r in sub.iterrows():
                prob = r[f"prob_{tag}"]
                add(f"| {r['id_part']} | {r['defect_type']} | {prob:.4f} |")
            add("")
    add("---")
    add("_Generated by `verification_report.py` using the latest trained S14 models._")
    _save(lines, out_report)


def write_report_all(quality, out_report):
    lines = []
    add = lines.append
    _headers(lines)
    add(f"- Scope: all parts of die **{DIE}**: **{len(quality)}** "
        f"(good: **{int(quality['defect_type'].isna().sum())}**, "
        f"defective: **{int(quality['defect_type'].notna().sum())}**)")
    n_computed = int(quality["defect_prediction_done"].sum())
    add(f"- Parts with operating parameters (prediction computed): **{n_computed}** "
        f"({len(quality) - n_computed} lack operating_parameter rows)")
    mapped = quality.dropna(subset=["mapped_defect"])
    n_na = int(quality["mapped_defect"].isna().sum())
    add(f"- Defective parts mappable to a target model: **{len(mapped)}**")
    add(f"- Parts without a mappable defect (good + unsupported defect names): **{n_na}** "
        f"(good: **{int(quality['defect_type'].isna().sum())}**, "
        f"defective with unsupported name: **{int(((quality['defect_type'].notna()) & quality['mapped_defect'].isna()).sum())}**)")
    add("")
    add("## Part-level results (all parts with a computable prediction)")
    add("")
    scored = quality[quality["accuracy"].notna()]
    n_scored = len(scored)
    correct = int(scored["accuracy"].sum())
    fp_parts = scored[(scored["accuracy"] == 0.0) & scored["defect_type"].isna()]
    fn_parts = scored[(scored["accuracy"] == 0.0) & scored["defect_type"].notna()]
    add(f"- Scored parts: **{n_scored}**")
    add(f"- Part-level **accuracy: {correct/n_scored*100:.2f}%** ({correct}/{n_scored})")
    add(f"- **False positives (good part flagged defective): {len(fp_parts)}**")
    add(f"- **False negatives (defective part's defect not predicted): {len(fn_parts)}**")
    add("")
    add("## Per-defect confusion matrix (positive = actual defect == that target)")
    add("")
    add("| Defect | Positives | True Pos | False Neg | True Neg | False Pos | Accuracy | Precision | Recall |")
    add("|---|---|--:|--:|--:|--:|--:|--:|--:|")
    for tag in TARGET_DEFECTS:
        done = quality["defect_prediction_done"].eq(1)
        actual = done & quality["mapped_defect"].eq(tag)
        pred = done & quality[f"pred_{tag}"].eq(1)
        tp = int((actual & pred).sum())
        fn = int((actual & ~pred).sum())
        tn = int((~actual & ~pred).sum())
        fp = int((~actual & pred).sum())
        n = tp + fn + tn + fp
        acc = (tp + tn) / n if n else 0.0
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        add(f"| {tag} | {tp+fn} | {tp} | **{fn}** | {tn} | **{fp}** | {acc*100:.2f}% | "
            f"{prec*100:.2f}% | {rec*100:.2f}% |")
    add("")
    add("_Note: a part with an unmapped defect name counts as negative for each target "
        "(training labels the 6 target defects only)._")
    add("")
    add("## False-negative parts (actual defect not predicted)")
    add("")
    fns = quality[(quality["accuracy"] == 0.0) & quality["defect_type"].notna()]
    if fns.empty:
        add("None.")
    else:
        for tag in TARGET_DEFECTS:
            sub = fns[fns["mapped_defect"] == tag]
            if sub.empty:
                continue
            add(f"### {tag} — {len(sub)} false negative{'s' if len(sub) != 1 else ''}")
            add("")
            add("| id_part | actual defect_type | probability assigned to actual defect |")
            add("|---|---|--:|")
            for _, r in sub.iterrows():
                add(f"| {r['id_part']} | {r['defect_type']} | {r[f'prob_{tag}']:.4f} |")
            add("")
    add("## False-positive parts (good part, but flagged defective)")
    add("")
    fpp = quality[(quality["accuracy"] == 0.0) & quality["defect_type"].isna()]
    if fpp.empty:
        add("None.")
    else:
        add(f"{len(fpp)} good parts were flagged (sample of {min(len(fpp), 50)} shown; "
            "full list in the CSV).")
        add("")
        add("| id_part | flagged defect | probability |")
        add("|---|---|--:|")
        for _, r in fpp.head(50).iterrows():
            flagged = next((t for t in TARGET_DEFECTS if r[f"pred_{t}"] == 1), None)
            add(f"| {r['id_part']} | {flagged} | {r[f'prob_{flagged}']:.4f} |")
        add("")
    add("---")
    add("_Generated by `verification_report.py` using the latest trained S14 models._")
    _save(lines, out_report)


def main():
    scopes = sys.argv[1:] or ["all"]
    for s in scopes:
        if s in ("defective", "all"):
            run(s)
        else:
            print(f"unknown scope: {s}")
            sys.exit(2)


if __name__ == "__main__":
    main()