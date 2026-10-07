"""Train, compare and evaluate lead-conversion models; export the production model + report."""
import json, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import roc_auc_score, roc_curve, brier_score_loss
from sklearn.calibration import calibration_curve
import joblib
from .features import featurize, FEATURES
from . import model_io, recommend

ROOT = Path(__file__).resolve().parent.parent


def precision_at(y, p, frac=.2):
    k = int(len(y) * frac)
    idx = np.argsort(-p)[:k]
    return float(np.mean(np.asarray(y)[idx]))


def evaluate(name, y, p):
    base = float(np.mean(y))
    pa = precision_at(y, p)
    k = int(len(y) * .2)
    capture = float(np.asarray(y)[np.argsort(-p)[:k]].sum() / np.sum(y))
    return {"model": name, "auc": round(roc_auc_score(y, p), 4), "precision_top20": round(pa, 4),
            "lift_top20": round(pa / base, 2), "conversions_captured_top20": round(capture, 4),
            "brier": round(brier_score_loss(y, p), 4)}


def main():
    df = pd.read_csv(ROOT / "data/leads_history.csv")
    X, y = featurize(df), df["Converted"]
    Xtr, Xte, ytr, yte, dtr, dte = train_test_split(X, y, df, test_size=.3, stratify=y, random_state=42)

    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(Xtr, ytr)
    gb = GradientBoostingClassifier(n_estimators=200, learning_rate=.06, max_depth=3, subsample=.8, random_state=42).fit(Xtr, ytr)
    p_lr, p_gb = lr.predict_proba(Xte)[:, 1], gb.predict_proba(Xte)[:, 1]
    results = [evaluate("Logistic regression (baseline)", yte, p_lr), evaluate("Gradient boosting (production)", yte, p_gb)]
    cv = cross_val_score(GradientBoostingClassifier(n_estimators=200, learning_rate=.06, max_depth=3, subsample=.8, random_state=42),
                         X, y, cv=5, scoring="roc_auc")
    print(pd.DataFrame(results).to_string(index=False)); print("5-fold CV AUC (GB):", cv.mean().round(4), "+/-", cv.std().round(4))

    # Export production model and verify the JSON model reproduces sklearn
    model = model_io.export_model(gb, FEATURES, float(ytr.mean()))
    diffs, adds = [], []
    for i in range(300):
        x = Xte.iloc[i].tolist()
        raw, c, bias = model_io.raw_and_contribs(model, x)
        diffs.append(abs(model_io.sigmoid(raw) - p_gb[i])); adds.append(abs(bias + sum(c) - raw))
    print("max |JSON prob - sklearn prob|:", max(diffs), "| max additivity error:", max(adds))
    assert max(diffs) < 1e-3 and max(adds) < 1e-6

    # Score the test set with the full recommendation engine
    scored = recommend.score_frame(model, dte)
    ev = dte.join(scored[["AI_Score__c", "AI_Priority__c", "Next_Best_Action__c"]])
    order = ["Very High", "High", "Medium", "Low"]
    tiers = [{"priority": t, "leads": int((ev.AI_Priority__c == t).sum()),
              "conversion_rate": round(float(ev[ev.AI_Priority__c == t].Converted.mean()), 3) if (ev.AI_Priority__c == t).any() else None}
             for t in order]
    print(pd.DataFrame(tiers).to_string(index=False))

    # Global importance = mean |contribution| over a sample
    imp = np.zeros(len(FEATURES))
    for i in range(500):
        _, c, _ = model_io.raw_and_contribs(model, Xte.iloc[i].tolist()); imp += np.abs(c)
    imp = (imp / 500)
    top = sorted(zip(FEATURES, imp), key=lambda t: -t[1])[:10]

    metrics = {"models": results, "cv_auc_mean": round(float(cv.mean()), 4), "test_size": int(len(yte)),
               "base_conversion_rate": round(float(y.mean()), 3), "tiers": tiers,
               "importance": [{"feature": f, "mean_abs_impact": round(float(v), 3)} for f, v in top]}
    model["metrics"] = metrics
    (ROOT / "models").mkdir(exist_ok=True)
    model_io.save(model, ROOT / "models/model.json")
    joblib.dump({"gb": gb, "lr": lr}, ROOT / "models/sklearn_models.joblib")
    json.dump(metrics, open(ROOT / "reports/metrics.json", "w"), indent=2)

    # Open leads sitting in the (mock) CRM: held-out leads the model never saw, outcome hidden
    open_leads = dte.sample(400, random_state=7)
    open_leads.drop(columns=["Converted"]).to_csv(ROOT / "data/crm_leads.csv", index=False)
    open_leads[["Id", "Converted"]].to_csv(ROOT / "data/crm_leads_truth.csv", index=False)

    # Charts
    (ROOT / "reports").mkdir(exist_ok=True)
    fig, ax = plt.subplots(2, 2, figsize=(11, 8.5))
    for p, n, c in [(p_lr, "Logistic regression", "#8aa3c7"), (p_gb, "Gradient boosting", "#0176d3")]:
        fpr, tpr, _ = roc_curve(yte, p); ax[0, 0].plot(fpr, tpr, label=f"{n} (AUC {roc_auc_score(yte, p):.3f})", color=c)
    ax[0, 0].plot([0, 1], [0, 1], "--", color="grey"); ax[0, 0].set(title="ROC curve", xlabel="False positive rate", ylabel="True positive rate"); ax[0, 0].legend()
    fr, mp = calibration_curve(yte, p_gb, n_bins=10)
    ax[0, 1].plot(mp, fr, "o-", color="#0176d3"); ax[0, 1].plot([0, 1], [0, 1], "--", color="grey")
    ax[0, 1].set(title="Calibration: predicted vs actual", xlabel="Predicted probability", ylabel="Actual conversion rate")
    ax[1, 0].bar([t["priority"] for t in tiers], [(t["conversion_rate"] or 0) * 100 for t in tiers], color=["#ba0517", "#dd7a01", "#0b7cc4", "#706e6b"])
    ax[1, 0].axhline(y.mean() * 100, ls="--", color="grey"); ax[1, 0].set(title="Actual conversion rate by priority tier (test set)", ylabel="% converted")
    ax[1, 1].barh([f for f, _ in top][::-1], [float(v) for _, v in top][::-1], color="#0176d3"); ax[1, 1].set(title="Top drivers (mean |impact| on log-odds)")
    plt.tight_layout(); plt.savefig(ROOT / "reports/model_report.png", dpi=130)
    print("saved model + report")


if __name__ == "__main__":
    main()
