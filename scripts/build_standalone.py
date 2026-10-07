"""Build one self-contained HTML file (model + leads embedded). python -m scripts.build_standalone"""
import json, pandas as pd
from pathlib import Path
from src import model_io
root = Path(__file__).resolve().parent.parent
model = model_io.load(root / "models/model.json")
leads = pd.read_csv(root / "data/crm_leads.csv").head(300)
leads = leads[[c for c in leads.columns if not c.endswith("__c") and c != "AI_Scored_At__c"]]
html = (root / "web/workbench.html").read_text()
payload = json.dumps({"model": model, "leads": leads.to_dict("records")}, separators=(",", ":"))
out = root / "dist"; out.mkdir(exist_ok=True)
(out / "leadlens_workbench.html").write_text(html.replace("/*EMBED*/null/*END*/", "/*EMBED*/" + payload + "/*END*/"))
print("dist/leadlens_workbench.html", round(len(payload) / 1024), "KB payload")
