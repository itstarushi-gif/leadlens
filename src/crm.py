"""CRM access layer. Uses real Salesforce when SF_* env vars are set, otherwise a local CSV acts as the mock CRM."""
import os, datetime as dt
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOCK = ROOT / "data/crm_leads.csv"
OUTCOMES = ROOT / "data/outcomes.csv"
AI_FIELDS = ["AI_Score__c", "Conversion_Probability__c", "AI_Priority__c", "Next_Best_Action__c", "Recommendation_Reason__c"]

# Salesforce API names -> the column names the model expects
SF_MAP = {"Id": "Id", "Name": "Name", "Company": "Company", "Title": "Title", "Industry": "Industry",
          "NumberOfEmployees": "NumberOfEmployees", "LeadSource": "LeadSource", "Seniority__c": "Seniority",
          "Email_Opens_14d__c": "Email_Opens_14d", "Email_Clicks_14d__c": "Email_Clicks_14d", "Web_Visits_14d__c": "Web_Visits_14d",
          "Pricing_Page_Visits__c": "Pricing_Page_Visits", "Form_Fills__c": "Form_Fills", "Previous_Touches__c": "Previous_Touches",
          "Campaign_Responses__c": "Campaign_Responses", "Days_Since_Last_Activity__c": "Days_Since_Last_Activity",
          "Days_Since_Created__c": "Days_Since_Created", "Has_Phone__c": "Has_Phone", "Free_Email_Domain__c": "Free_Email_Domain",
          "Requested_Demo__c": "Requested_Demo"}


def live():
    return all(os.getenv(k) for k in ("SF_USERNAME", "SF_PASSWORD", "SF_TOKEN"))


def _sf():
    from simple_salesforce import Salesforce
    return Salesforce(username=os.environ["SF_USERNAME"], password=os.environ["SF_PASSWORD"],
                      security_token=os.environ["SF_TOKEN"], domain=os.getenv("SF_DOMAIN", "login"))


def fetch_open_leads(limit=500) -> pd.DataFrame:
    if live():
        soql = f"SELECT {', '.join(SF_MAP)} FROM Lead WHERE IsConverted = false LIMIT {limit}"
        recs = _sf().query_all(soql)["records"]
        df = pd.DataFrame(recs).drop(columns="attributes", errors="ignore").rename(columns=SF_MAP)
        return df.fillna({"NumberOfEmployees": 1})
    return pd.read_csv(MOCK).head(limit)


def write_scores(scored: pd.DataFrame):
    """scored: index/Id plus AI_* columns. Pushes the AI fields back onto the Lead records."""
    now = dt.datetime.utcnow().isoformat()
    if live():
        rows = [{"Id": r.Id, **{f: getattr(r, f) for f in AI_FIELDS}, "AI_Scored_At__c": now + "Z"} for r in scored.itertuples()]
        return _sf().bulk.Lead.update(rows)
    cur = pd.read_csv(MOCK)
    for f in AI_FIELDS + ["AI_Scored_At__c"]:
        if f not in cur: cur[f] = None
    s = scored.set_index("Id")
    for f in AI_FIELDS:
        cur[f] = cur.Id.map(s[f]).combine_first(cur[f])
    cur["AI_Scored_At__c"] = now
    cur.to_csv(MOCK, index=False)
    return len(s)


def update_lead(lead_id: str, fields: dict):
    if live():
        rev = {v: k for k, v in SF_MAP.items()}
        return _sf().Lead.update(lead_id, {rev[k]: v for k, v in fields.items() if k in rev})
    cur = pd.read_csv(MOCK)
    for k, v in fields.items():
        if k in cur: cur.loc[cur.Id == lead_id, k] = v
    cur.to_csv(MOCK, index=False)


def log_outcome(lead_id: str, action: str, result: str, score: int):
    """The feedback loop: every SDR outcome is stored so the model can be retrained on it."""
    row = pd.DataFrame([{"timestamp": dt.datetime.utcnow().isoformat(), "Id": lead_id, "action": action, "result": result, "score_at_time": score}])
    row.to_csv(OUTCOMES, mode="a", header=not OUTCOMES.exists(), index=False)
    if live():
        _sf().Task.create({"WhoId": lead_id, "Subject": f"{action} - {result}", "Status": "Completed"})
