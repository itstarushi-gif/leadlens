"""Turn raw Salesforce Lead fields into model features. Mirrored exactly in web/workbench.html."""
import numpy as np, pandas as pd
from .generate_data import INDUSTRIES, SOURCES, SENIORITY

NUMERIC = ["seniority_level", "log_employees", "email_opens", "email_clicks", "web_visits", "pricing_visits",
           "form_fills", "previous_touches", "campaign_responses", "days_since_activity", "days_since_created",
           "has_phone", "free_email", "requested_demo"]
FEATURES = NUMERIC + [f"industry_{i}" for i in INDUSTRIES] + [f"source_{s}" for s in SOURCES]

RAW_TO_NUM = {"email_opens": "Email_Opens_14d", "email_clicks": "Email_Clicks_14d", "web_visits": "Web_Visits_14d",
              "pricing_visits": "Pricing_Page_Visits", "form_fills": "Form_Fills", "previous_touches": "Previous_Touches",
              "campaign_responses": "Campaign_Responses", "days_since_activity": "Days_Since_Last_Activity",
              "days_since_created": "Days_Since_Created", "has_phone": "Has_Phone", "free_email": "Free_Email_Domain",
              "requested_demo": "Requested_Demo"}


def featurize(df: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    X["seniority_level"] = df["Seniority"].map({s: i for i, s in enumerate(SENIORITY)}).fillna(0).astype(float)
    X["log_employees"] = np.log1p(df["NumberOfEmployees"].astype(float).clip(lower=1))
    for k, col in RAW_TO_NUM.items():
        X[k] = df[col].astype(float)
    for i in INDUSTRIES:
        X[f"industry_{i}"] = (df["Industry"] == i).astype(float)
    for s in SOURCES:
        X[f"source_{s}"] = (df["LeadSource"] == s).astype(float)
    return X[FEATURES]
