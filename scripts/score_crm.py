"""Batch job: score all open leads and write AI fields back to the CRM.  python -m scripts.score_crm"""
import pandas as pd
from src import crm, model_io, recommend

model = model_io.load(crm.ROOT / "models/model.json")
df = crm.fetch_open_leads(5000)
sc = recommend.score_frame(model, df)
crm.write_scores(pd.concat([df[["Id"]].reset_index(drop=True), sc.reset_index(drop=True)], axis=1))
print(f"Scored {len(df)} leads in {'Salesforce' if crm.live() else 'mock CRM'}")
print(sc.AI_Priority__c.value_counts().to_string())
