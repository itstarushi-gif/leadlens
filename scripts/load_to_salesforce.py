"""Load the synthetic leads into a Salesforce Developer org (needs SF_* env vars and the custom fields deployed).
python -m scripts.load_to_salesforce 500"""
import sys, pandas as pd
from src import crm
n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
df = pd.read_csv(crm.ROOT / "data/crm_leads.csv").head(n)
rev = {v: k for k, v in crm.SF_MAP.items()}
df["LastName"] = df.Name.str.split().str[-1]
rows = []
for r in df.to_dict("records"):
    row = {rev[k]: v for k, v in r.items() if k in rev and k not in ("Id", "Name")}
    row.update({"LastName": r["LastName"], "FirstName": r["Name"].split()[0], "Status": "Open - Not Contacted"})
    rows.append({k: (int(v) if hasattr(v, "item") and isinstance(v.item(), int) else v) for k, v in row.items()})
print(crm._sf().bulk.Lead.insert(rows)[:3], f"... inserted {len(rows)} leads")
