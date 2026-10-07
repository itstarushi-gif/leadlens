"""Lead score -> priority, Next Best Action and a plain-English reason. Mirrored in web/workbench.html."""
import numpy as np, pandas as pd
from . import model_io
from .features import featurize

MIN_CONTRIB = 0.15


def priority(score):
    return "Very High" if score >= 90 else "High" if score >= 75 else "Medium" if score >= 50 else "Low"


def action(score):
    if score >= 90: return "Call the lead"
    if score >= 80: return "Schedule a demo"
    if score >= 70: return "Send personalized email"
    if score >= 50: return "Follow up later"
    return "Put into nurture"


def _phrase(name, v, pos, lead):
    n = int(v)
    if name == "seniority_level": return f"Senior decision maker ({lead['Title']})" if pos else f"Junior role ({lead['Title']})"
    if name == "log_employees":
        e = f"{int(lead['NumberOfEmployees']):,}"
        return f"Good-fit company size ({e} employees)" if pos else f"Small company ({e} employees)"
    t = {
        "email_opens": (f"Opened {n} emails", "Few email opens"),
        "email_clicks": (f"Clicked {n} email links", "No email clicks"),
        "web_visits": (f"{n} website visits", "Little website activity"),
        "pricing_visits": (f"Viewed pricing page {n}x", "Never viewed pricing"),
        "form_fills": (f"Filled {n} form(s)", "No form fills"),
        "previous_touches": (f"{n} prior touches", "No prior touches"),
        "campaign_responses": (f"Responded to {n} campaigns", "No campaign response"),
        "days_since_activity": ("Active today" if n == 0 else f"Active {n} days ago", f"No activity for {n} days"),
        "days_since_created": (f"Fresh lead ({n} days old)", f"Aging lead ({n} days old)"),
        "has_phone": ("Phone on file", "No phone number"),
        "free_email": ("Business email", "Free email domain"),
        "requested_demo": ("Requested a demo", "No demo request"),
    }
    if name in t: return t[name][0 if pos else 1]
    if name.startswith("industry_"): return f"{name[9:]} industry fits target" if pos else f"{name[9:]} industry is a weaker fit"
    if name.startswith("source_"): return f"Source: {name[7:]}" if pos else f"Source: {name[7:]} converts less"
    return name


def build_reason(model, x, contribs, score, lead):
    cand = []
    for i, name in enumerate(model["features"]):
        if name.startswith(("industry_", "source_")) and x[i] != 1:
            continue
        cand.append((name, x[i], contribs[i]))
    pos = sorted([c for c in cand if c[2] > MIN_CONTRIB], key=lambda c: -c[2])[:3]
    neg = sorted([c for c in cand if c[2] < -MIN_CONTRIB], key=lambda c: c[2])[:2]
    if score >= 50:
        parts = [_phrase(n, v, True, lead) for n, v, _ in pos] or ["Balanced signals"]
    else:
        parts = [_phrase(n, v, False, lead) for n, v, _ in neg] or ["Few buying signals"]
    return " + ".join(parts)


def score_lead(model, lead: dict):
    """lead: dict with Salesforce field names. Returns the AI fields written back to Salesforce."""
    X = featurize(pd.DataFrame([lead]))
    x = [float(v) for v in X.iloc[0][model["features"]]]
    raw, contribs, bias = model_io.raw_and_contribs(model, x)
    prob = model_io.sigmoid(raw)
    score = int(round(prob * 100))
    act, reason = action(score), build_reason(model, x, contribs, score, lead)
    if act == "Call the lead" and not int(lead.get("Has_Phone", 1)):
        act, reason = "Send personalized email", reason + " (no phone on file)"
    top = sorted(zip(model["features"], contribs), key=lambda c: -abs(c[1]))[:8]
    return {"AI_Score__c": score, "Conversion_Probability__c": round(prob, 4), "AI_Priority__c": priority(score),
            "Next_Best_Action__c": act, "Recommendation_Reason__c": reason,
            "drivers": [{"feature": n, "impact": round(c, 3)} for n, c in top]}


def score_frame(model, df: pd.DataFrame):
    rows = [score_lead(model, r) for r in df.to_dict("records")]
    return pd.DataFrame(rows, index=df.index)
