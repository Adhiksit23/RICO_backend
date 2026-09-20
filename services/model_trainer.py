import pandas as pd
import numpy as np
import warnings, re, os
from collections import Counter
from sklearn.ensemble        import RandomForestClassifier, VotingClassifier
from sklearn.linear_model    import LogisticRegression
try:
    from lightgbm import LGBMClassifier
except: os.system("pip install lightgbm -q"); from lightgbm import LGBMClassifier
try:
    from xgboost import XGBClassifier
except: os.system("pip install xgboost -q"); from xgboost import XGBClassifier
warnings.filterwarnings("ignore")
import psycopg2
import pickle
import matplotlib.pyplot as plt
from datetime import date as  _date_cls, timedelta, timezone

from sklearn.decomposition import PCA
from sklearn.cross_decomposition import CCA
from sklearn.preprocessing   import MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics         import (confusion_matrix, classification_report,
                                     ConfusionMatrixDisplay, fbeta_score)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "models")
from .config import DB_CONFIG


PARAM_COLS = [
    "cycletime value (sec)",
    "DIE CLOSE/CORE IN Parameter (sec)value",
    "POURING-step value (sec)",
    "SHOT FWD-step value (sec)",
    "COOLING-step value (sec)",
    "DIE OPEN/CORE OUT-step value (sec)",
    "EJECTOR-step value (sec)",
    "EXTRACTOR-step value (sec)",
    "SPRAY-step value (sec)",
    "SPEED 1 (m/sec)value",
    "SPEED 2 (m/sec)value",
    "SPEED 3 (m/sec)value",
    "SPEED 4(m/sec)value",
    "ACC POSITION 1(mm)value",
    "DEACC POSITION 1(mm)value",
    "INTESIFICAITON TIME(msec)value",
    "MATEL PRESSURE(Mpa)value",
    "BISCUIT THICKNESS(mm)value",
    "CLAMP FORCE(%)value",
    "CLAMP TONNAGE(MN)value",
    "SHOT ACC. PRESSURE value",
    "INTESIFICAITON ACC. PRESSUREvalue",
    "METAL TEMP.value",
]

TARGET_DEFECTS = ["Blow Hole","Crack","Non filling","Porosity","Shrinkage","Chipoff"]
MODEL_ORDER    = ["Logistic Regression","Gaussian NB","Decision Tree",
                    "Random Forest","LightGBM","XGBoost","Voting Ensemble"]

def safe_cn(col):
    return re.sub(r"[^a-zA-Z0-9]", "_", str(col)).strip("_").replace("__", "_")

def get_pca_component(input_rescaled):
    pca = PCA().fit(input_rescaled)
    cum_var = np.cumsum(pca.explained_variance_ratio_)
    idx = np.where(cum_var >= 0.95)[0]
    get_component = int(idx[0]) + 1 if len(idx) else 1
    return get_component

def best_threshold(y_true, y_prob, fixed_t=0.4):
    return fixed_t

def get_models(n_pos, n_neg):
    # Note: no scale_pos_weight needed — training is 1:1 balanced after undersampling
    return {
        "Logistic Regression": LogisticRegression(
            max_iter=1000, C=0.1, random_state=42),
        #"Gaussian NB" : GaussianNB(),
        # "Decision Tree": DecisionTreeClassifier(
        #     max_depth=5, random_state=42),
        "Random Forest": RandomForestClassifier(
            n_estimators=200, max_depth=6,
            random_state=42, n_jobs=-1),
        "LightGBM": LGBMClassifier(
            n_estimators=400, learning_rate=0.05, max_depth=5,
            random_state=42, verbose=-1),
        "XGBoost": XGBClassifier(
            n_estimators=400, learning_rate=0.05, max_depth=5,
            random_state=42, eval_metric="logloss", verbosity=0),
    }
def main(machine_id, die):

    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()

    print(
                "\nDatabase connection Opened."
            )
    
    num_samples = 0

    #Adjusts so that it takes for specific die and machine
    query = """
        SELECT c.*
        FROM operating_parameter c
        WHERE id_part IN (
            SELECT id_part FROM part
            WHERE id_die = %s and id_machine = %s
        );

    """
    #All Parts operating parameters
    df_raw = pd.read_sql(query, conn, params=(die, machine_id))
    df = df_raw.pivot(index=["id_part", "id_die"], columns="parameter_name", values="value")
    param_names = [col for col in df.columns if col not in ["id_part", "id_die"]]
    df_data = df.reset_index()
    print('Rows (parts):', len(df_data))
    # print('Columns:', len(df_data.columns))
    # print('First row:')
    # print(df_data.iloc[0])

    print(
            "\nRecieved All Part Data."
    )

    for defect in TARGET_DEFECTS:
        df_data[safe_cn(defect)] = 0

    #Parts with defects:
    cur.execute(
    "SELECT id_part, defect_type FROM part_quality WHERE id_die = %s AND id_machine = %s",(die, machine_id),)
    rows_defects = cur.fetchall()

    def normalize_defect(name):
        return re.sub(r"[^a-zA-Z0-9]", "", str(name)).lower()

    def match_target_defect(name):
        normalized = normalize_defect(name)
        for target in TARGET_DEFECTS:
            if normalize_defect(target) in normalized:
                return target
        return None

    defect_mapping = {}
    matched_rows   = []
    for id_part, defect_type in rows_defects:
        if str(defect_type).upper().startswith("PLC_COMMUNICATION"):
            continue
        target = match_target_defect(defect_type)
        if target is not None:
            defect_mapping[defect_type] = target
            matched_rows.append((id_part, target))

    print("\nDefect name -> target defect matching:")
    for defect_type, target in defect_mapping.items():
        print(f"  {defect_type!r:55} -> {target}")

    print(f"\nUnique defect names matched: {len(defect_mapping)}")
    print(f"Matched defective parts: {len(matched_rows)}")

    existing_ids = {row[0] for row in matched_rows}
    id_to_reason = {row[0]: row[1] for row in matched_rows}

    target_col = {defect: safe_cn(defect) for defect in TARGET_DEFECTS}

    defect_index = df_data.set_index("id_part")
    for id_part, target in matched_rows:
        defect_index.at[id_part, target_col[target]] = 1
    df_data = defect_index.reset_index()

    labeled_counts = df_data[list(target_col.values())].sum()
    print("\nLabeled parts per defect column:")
    for col, total in labeled_counts.items():
        print(f"  {col}: {int(total)}")

    matched_counts = Counter(target for _, target in matched_rows)
    print("\nCounts per target defect (matched only):")
    for defect, count in matched_counts.items():
        print(f"  {defect}: {count}")

    print(
                "\nRecieved All Defect Part id Data."
        )

    print(f"Defective part ids: {len(existing_ids)}")

    query = """
        SELECT c.parameter_name, c.baseline, c.upper_tolerance, c.lower_tolerance
        FROM calibration_parameter c
        WHERE c.id_die = %s
        AND c.id_calibration = (
          SELECT MAX(id_calibration)
          FROM calibration_parameter
          WHERE id_die = %s
        ) """

    df_baselines = pd.read_sql(query, conn, params=(die, die))
    baselines = {
        r["parameter_name"]: (r["baseline"], r["lower_tolerance"], r["upper_tolerance"])
        for _, r in df_baselines.iterrows()
    }
    print(f"\nBaselines loaded for die {die}: {len(baselines)} params")

    clean_datasets = {defect: (df_data, PARAM_COLS) for defect in TARGET_DEFECTS}

    feat_datasets = {}
    for defect, (d, params) in clean_datasets.items():
        bl_die = baselines
        feat_rows = []

        for _, row in d.iterrows():
            bl = bl_die
            feats = {}
            for col, (avg, min_r, max_r) in bl.items():
                val = pd.to_numeric(row.get(col, np.nan), errors="coerce")
                cn  = safe_cn(col)
                if pd.isna(val):
                    feats[f"{cn}_inrange"] = 0
                    feats[f"{cn}_pctdev"]  = 0.0
                else:
                    feats[f"{cn}_inrange"] = int(min_r <= val <= max_r)
                    pct = (val - avg) / avg if avg != 0 else 0.0
                    feats[f"{cn}_pctdev"] = float(np.clip(pct, -0.30, 0.30))
            feat_rows.append(feats)

        feat_df = pd.DataFrame(feat_rows, index=d.index)
        feat_df["id_die"] = d["id_die"].values
        feat_df[safe_cn(defect)] = d[safe_cn(defect)].values
        feat_datasets[defect] = feat_df
        print(f"\n[{defect}] feat_df: {feat_df.shape[0]} rows x {feat_df.shape[1]} cols")
        print(feat_df.head(2))

    splits = {}


    for defect, feat_df in feat_datasets.items():
        label_col = safe_cn(defect)
        FC = [c for c in feat_df.columns if c not in ["id_part", "id_die", label_col]]
        y  = feat_df[label_col]

        pos_idx = y[y==1].index.tolist()
        neg_idx = y[y==0].index.tolist()

        if len(pos_idx) < 10:
            continue

        # ── Step 1: Undersample good rows to match defect count (1:1) ─────────
        n_defects = len(pos_idx)
        rng = np.random.RandomState(42)
        n_neg = min(n_defects, len(neg_idx))
        neg_sampled = rng.choice(neg_idx, size=n_neg, replace=False).tolist()

        # ── Step 2: Combine and do a simple 70/30 split ────────────────────────
        balanced_idx = sorted(pos_idx + neg_sampled)
        tr_idx, te_idx = train_test_split(balanced_idx, test_size=0.30,
                                        random_state=42)

        X_raw_tr = feat_df.loc[tr_idx, FC].fillna(0)
        X_raw_te = feat_df.loc[te_idx, FC].fillna(0)
        y_tr     = y.loc[tr_idx]
        y_te     = y.loc[te_idx]

        scaler = MinMaxScaler()
        X_tr   = pd.DataFrame(scaler.fit_transform(X_raw_tr),
                            columns=FC, index=tr_idx)
        X_te   = pd.DataFrame(scaler.transform(X_raw_te),
                            columns=FC, index=te_idx)

        splits[defect] = (X_tr, X_te, y_tr, y_te, FC, scaler)

    # ── PCA per defect → train all models ─────────────────────────────────────
    splits_pca = {}


    for defect, (X_tr, X_te, y_tr, y_te, FC, scaler) in splits.items():

        print(f"\n-- {defect} {'-'*(50-len(defect))}")

        X_tr_arr = X_tr.fillna(0).values
        X_te_arr = X_te.fillna(0).values

        # ── Find optimal n_components using training data only ────────────────
        n_comp = get_pca_component(X_tr_arr)
        
        # ── Fit PCA on train, transform both train and test ───────────────────
        pca = PCA(n_components=n_comp, random_state=42)
        X_tr_pca = pca.fit_transform(X_tr_arr)
        X_te_pca = pca.transform(X_te_arr)          # no leakage — fit on train only

        pca_cols = [f"PCA_{i+1}" for i in range(n_comp)]
        X_tr_pca_df = pd.DataFrame(X_tr_pca, columns=pca_cols)
        X_te_pca_df = pd.DataFrame(X_te_pca, columns=pca_cols)

        print(f"  Shape: {X_tr_arr.shape} -> train {X_tr_pca_df.shape} | test {X_te_pca_df.shape}")

        y_tr_reset = y_tr.reset_index(drop=True)
        y_te_reset = y_te.reset_index(drop=True)

        splits_pca[defect] = (X_tr_pca_df, X_te_pca_df, y_tr_reset, y_te_reset, pca, pca_cols, scaler)

        
    splits_pca_cca = {}

    for defect, (
            X_tr_pca_df,
            X_te_pca_df,
            y_tr,
            y_te,
            pca,
            pca_cols,
            scaler
        ) in splits_pca.items():

        print(f"\n── {defect} {'─'*(50-len(defect))}")

        # =========================================================
        # Convert labels to numerical multi-dimensional form
        # =========================================================

        y_tr_cca = pd.get_dummies(y_tr)

        # =========================================================
        # Decide number of CCA components
        # =========================================================

        n_cca = min(
            X_tr_pca_df.shape[1],
            y_tr_cca.shape[1]
        )

        print(f"  CCA Components: {n_cca}")

        # =========================================================
        # Create CCA model
        # =========================================================

        cca = CCA(n_components=n_cca)

        # =========================================================
        # FIT ONLY ON TRAIN
        # =========================================================

        X_tr_cca, _ = cca.fit_transform(
            X_tr_pca_df,
            y_tr_cca
        )

        # =========================================================
        # TEST IS BLIND
        # ONLY TRANSFORM TEST
        # =========================================================

        X_te_cca = cca.transform(X_te_pca_df)

        # =========================================================
        # Convert to dataframe
        # =========================================================

        cca_cols = [f"CCA_{i+1}" for i in range(n_cca)]

        X_tr_cca_df = pd.DataFrame(
            X_tr_cca,
            columns=cca_cols
        )

        X_te_cca_df = pd.DataFrame(
            X_te_cca,
            columns=cca_cols
        )

        # =========================================================
        # Print shapes
        # =========================================================

        print(
            f"  PCA Shape : {X_tr_pca_df.shape}"
        )

        print(
            f"  CCA Shape : {X_tr_cca_df.shape}"
        )

        # =========================================================
        # Store results
        # =========================================================

        splits_pca_cca[defect] = (
            X_tr_cca_df,
            X_te_cca_df,
            y_tr.reset_index(drop=True),
            y_te.reset_index(drop=True),
            cca_cols,
            scaler,
            pca,
            cca
        )

    all_trained = {}

    for defect, (X_tr, X_te, y_tr, y_te, FC, scaler, pca, cca) in splits_pca_cca.items():
        n_pos = int(y_tr.sum()); n_neg = int((y_tr==0).sum())
       
        trained = {}
        for name, model in get_models(n_pos, n_neg).items():
            model.fit(X_tr, y_tr)
            p_te = model.predict_proba(X_te)[:,1]
            t = best_threshold(y_te, p_te)
            trained[name] = (model, p_te, y_te, t)
          
        voter = VotingClassifier(estimators=[
            ("lr",   LogisticRegression(max_iter=1000,C=0.1,random_state=42)),
            # ("gnb",  GaussianNB()),
            # ("dt",   DecisionTreeClassifier(max_depth=5,random_state=42)),
            ("rf",   RandomForestClassifier(n_estimators=200,max_depth=6,
                    random_state=42,n_jobs=-1)),
            ("lgbm", LGBMClassifier(n_estimators=400,learning_rate=0.05,
                    max_depth=5,random_state=42,verbose=-1)),
            ("xgb",  XGBClassifier(n_estimators=400,learning_rate=0.05,
                    max_depth=5,random_state=42,
                    eval_metric="logloss",verbosity=0)),
        ], voting="soft")
        voter.fit(X_tr, y_tr)
        p_v = voter.predict_proba(X_te)[:,1]
        t_v = best_threshold(y_te, p_v)
        trained["Voting Ensemble"] = (voter, p_v, y_te, t_v)
        all_trained[defect] = trained

        for defect, trained in all_trained.items():

            n_models = len(trained)
            n_cols = 4; n_rows = (n_models + n_cols - 1) // n_cols
            fig, axes = plt.subplots(n_rows, n_cols, figsize=(5*n_cols, 4.5*n_rows))
            axes = np.array(axes).flatten()

            for ax_i, name in enumerate(MODEL_ORDER):
                if name not in trained: continue
                model, p_te, y_te, t = trained[name]
                y_pred = (p_te >= t).astype(int)
                cm     = confusion_matrix(y_te, y_pred, labels=[0,1])
                tn, fp, fn, tp = cm.ravel()
                rec = tp / max(tp+fn, 1)
                far = fp / max(tn+fp, 1)

                # ── Text output — confusion matrix + report ────────────────────
                print(f"\n  {name}")
                print(f"  {'─'*45}")
                print(f"  Best Threshold: {t}")
                print(f"  Confusion Matrix:")
                print(f"  [[{tn}  {fp}]")
                print(f"   [{fn}   {tp}]]")
                print(classification_report(y_te, y_pred, zero_division=0,
                                            target_names=["Good", defect]))

    for defect, trained in all_trained.items():
        if "Voting Ensemble" not in trained:
            continue

        _, p_te, y_te, t = trained["Voting Ensemble"]
        y_pred = (p_te >= t).astype(int)
        y_te_arr   = np.array(y_te)
        p_te_arr   = np.array(p_te)

        # False Positives — actual=0, predicted=1
        fp_mask    = (y_te_arr == 0) & (y_pred == 1)
        fp_probs   = p_te_arr[fp_mask]

        # False Negatives — actual=1, predicted=0
        fn_mask    = (y_te_arr == 1) & (y_pred == 0)
        fn_probs   = p_te_arr[fn_mask]

        print(f"\n  {defect}")
        print(f"  {'─'*45}")
        print(f"  False Positives : {fp_mask.sum():4}  |  Avg prob = {fp_probs.mean():.4f}  |  Min = {fp_probs.min():.4f}  |  Max = {fp_probs.max():.4f}" if fp_mask.sum() > 0 else f"  False Positives : 0")
        print(f"  False Negatives : {fn_mask.sum():4}  |  Avg prob = {fn_probs.mean():.4f}  |  Min = {fn_probs.min():.4f}  |  Max = {fn_probs.max():.4f}" if fn_mask.sum() > 0 else f"  False Negatives : 0")


    _today = _date_cls.today().strftime("%Y%m%d")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 65)
    print(f"SAVING VOTING MODELS — date: {_today}")
    print("=" * 65)

    for defect, trained in all_trained.items():
        if "Voting Ensemble" not in trained:
            print(f"  ⚠️  {defect}: no Voting Ensemble — skip")
            continue

        voter_model, _, _, threshold = trained["Voting Ensemble"]

        # Unpack splits_pca_cca — 8 values
        _, _, _, _, cca_cols, scaler, pca, cca = splits_pca_cca[defect]
        # Get pca_cols from splits_pca
        _, _, _, _, pca_cols, _, _ = splits_pca[defect]

        save_obj = {
            "model"      : voter_model,
            "die"        : die,
            "defect"     : defect,
            "trained_on" : _today,
            "scaler"     : scaler,      # MinMaxScaler — step 1
            "pca"        : pca,         # PCA object   — step 2
            "pca_cols"   : pca_cols,
            "cca"        : cca,         # CCA object   — step 3
            "cca_cols"   : cca_cols,
            "threshold"  : threshold,
            "model_type" : "VotingClassifier (soft) — LR + RF + LGBM + XGB",
            "pipeline"   : "Raw → MinMaxScale → PCA(95%) → CCA → VotingClassifier",
        }
        print(defect)
        print("PCA components:", pca.n_components_)
        print("CCA expects:", cca.n_features_in_)

        tag   = defect.replace(" ", "_")
        die_dir  = os.path.join(OUTPUT_DIR, die)
        os.makedirs(die_dir, exist_ok=True)
        fname = f"{die}_{tag}_{_today}_voting.pkl"
        fpath = os.path.join(die_dir, fname)
        with open(fpath, "wb") as fh:
            pickle.dump(save_obj, fh)
        print(f"  ✅ {fname}")

    print(f"\nAll voting models saved to: {OUTPUT_DIR}")
    print(f"Naming: {{die}}_{{defect}}_{{YYYYMMDD}}_voting.pkl")
    print(f"\nTo load and predict:")
    print(f"  obj = pickle.load(open('Blow_Hole_YYYYMMDD_voting.pkl','rb'))")
    print(f"  X_scaled = obj['scaler'].transform(X_raw)")
    print(f"  X_pca    = obj['pca'].transform(X_scaled)")
    print(f"  X_cca    = obj['cca'].transform(X_pca)")
    print(f"  prob     = obj['model'].predict_proba(X_cca)[:,1]")
    print(f"  pred     = (prob >= obj['threshold']).astype(int)")
    return

if __name__ == "__main__":
    main("UBE 850T-2", "S14")