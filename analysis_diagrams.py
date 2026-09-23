import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay

TARGET_DEFECTS = ["Blow_Hole", "Crack", "Non_filling", "Porosity", "Shrinkage", "Chipoff"]
THRESHOLD = 0.40
OUT_DIR = "analysis"
CSV_ALL = "S14_all_parts_predictions.csv"
CSV_DEFECTIVE = "S14_part_quality_predictions.csv"

SCOPES = [
    ("all",       CSV_ALL,       "all parts"),
    ("defective", CSV_DEFECTIVE, "defective parts"),
]

plt.rcParams["font.size"] = 9


def load(scope):
    if scope == "all":
        df = pd.read_csv(CSV_ALL, dtype={"id_part": str})
    else:
        df = pd.read_csv(CSV_DEFECTIVE, dtype={"id_part": str})
    return df


def metrics_for(df, d):
    actual = df["mapped_defect"].eq(d).astype(int)
    pred = df[f"pred_{d}"].eq(1).astype(int)
    tn, fp, fn, tp = confusion_matrix(actual, pred, labels=[0, 1]).ravel()
    prec = tp / (tp + fp) if (tp + fp) else np.nan
    rec = tp / (tp + fn) if (tp + fn) else np.nan
    f1 = 2 * prec * rec / (prec + rec) if (prec is not np.nan and (prec + rec)) else np.nan
    if not (prec == prec) or not (rec == rec):
        f1 = np.nan
    else:
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else np.nan
    acc = (tp + tn) / (tn + fp + fn + tp)
    return dict(n=int(tn + fp + fn + tp), tn=int(tn), fp=int(fp),
                fn=int(fn), tp=int(tp), prec=prec, rec=rec, f1=f1, acc=acc)


def cm_figure(scope, label, rows):
    n = len(TARGET_DEFECTS)
    n_cols = 3
    n_rows = int(np.ceil(n / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4.5 * n_rows))
    axes = np.array(axes).flatten()
    for i, d in enumerate(TARGET_DEFECTS):
        m = rows[d]
        cm = np.array([[m["tn"], m["fp"]], [m["fn"], m["tp"]]])
        disp = ConfusionMatrixDisplay(cm, display_labels=["Good", d[:10]])
        disp.plot(ax=axes[i], colorbar=False, cmap="Blues")
        axes[i].set_title(
            f"{d}\nt={THRESHOLD} | Recall={m['rec']:.3f} | Precision={m['prec']:.3f} | F1={m['f1']:.3f}\n"
            f"Caught={m['tp']}/{m['tp'] + m['fn']}  (all-parts view: FP={m['fp']}, TN={m['tn']})",
            fontsize=7.5, fontweight="bold")
    for i in range(n, len(axes)):
        axes[i].set_visible(False)
    plt.suptitle(f"Confusion Matrices — {label}", fontsize=12, fontweight="bold")
    plt.tight_layout()
    path = os.path.join(OUT_DIR, f"S14_{scope}_confusion_grid.png")
    plt.savefig(path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")

    for i, d in enumerate(TARGET_DEFECTS):
        m = rows[d]
        cm = np.array([[m["tn"], m["fp"]], [m["fn"], m["tp"]]])
        fig, ax = plt.subplots(figsize=(4.2, 3.6))
        disp = ConfusionMatrixDisplay(cm, display_labels=["Good", d[:10]])
        disp.plot(ax=ax, colorbar=False, cmap="Blues")
        ax.set_title(
            f"{d}\nt={THRESHOLD} | Recall={m['rec']:.3f} | Precision={m['prec']:.3f} | F1={m['f1']:.3f}",
            fontsize=8, fontweight="bold")
        plt.tight_layout()
        path = os.path.join(OUT_DIR, f"S14_{scope}_CM_{d}.png")
        plt.savefig(path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved: {path}")


def metrics_figure(scope, label, rows):
    defects = TARGET_DEFECTS
    x = np.arange(len(defects))
    width = 0.26
    precs = [rows[d]["prec"] for d in defects]
    recs = [rows[d]["rec"] for d in defects]
    f1s = [rows[d]["f1"] for d in defects]

    fig, ax = plt.subplots(figsize=(10, 5))
    b1 = ax.bar(x - width, precs, width, label="Precision", color="#1f77b4")
    b2 = ax.bar(x, recs, width, label="Recall", color="#2ca02c")
    b3 = ax.bar(x + width, f1s, width, label="F1-score", color="#ff7f0e")
    for bars in (b1, b2, b3):
        for b in bars:
            v = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, v + 0.01,
                    f"{v:.2f}" if v == v else "-", ha="center", va="bottom", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels(defects, rotation=15, ha="right")
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("Score")
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.3)
    ax.set_title(f"S14 — {label} — Precision / Recall / F1-score (t={THRESHOLD})",
                 fontsize=12, fontweight="bold")
    plt.tight_layout()
    path = os.path.join(OUT_DIR, f"S14_{scope}_metrics.png")
    plt.savefig(path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for scope, path, label in SCOPES:
        df = load(scope)
        rows = {d: metrics_for(df, d) for d in TARGET_DEFECTS}
        print(f"\n{'='*70}\nScope: {label} ({len(df)} parts in {path})\n{'='*70}")
        print(f"| {'Defect':<12} | {'n':>6} | {'TP':>4} | {'FN':>4} | {'TN':>5} | "
              f"{'FP':>5} | {'Acc':>6} | {'Prec':>6} | {'Rec':>6} | {'F1':>6} |")
        print("|" + "---|" * 10)
        for d in TARGET_DEFECTS:
            m = rows[d]
            fmt = lambda v: f"{v:.3f}" if v == v else "-"
            print(f"| {d:<12} | {m['n']:>6} | {m['tp']:>4} | {m['fn']:>4} | {m['tn']:>5} | "
                  f"{m['fp']:>5} | {fmt(m['acc']):>6} | {fmt(m['prec']):>6} | "
                  f"{fmt(m['rec']):>6} | {fmt(m['f1']):>6} |")
        cm_figure(scope, label, rows)
        metrics_figure(scope, label, rows)


if __name__ == "__main__":
    main()