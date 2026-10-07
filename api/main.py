"""LeadLens scoring API.  Run:  uvicorn api.main:app --reload   then open http://127.0.0.1:8000"""
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from src import crm, model_io, recommend

ROOT = Path(__file__).resolve().parent.parent
MODEL = model_io.load(ROOT / "models/model.json")
app = FastAPI(title="LeadLens", version="1.0", description="AI lead scoring and next best action for Salesforce")


class Lead(BaseModel):
    Id: str | None = None
    Name: str = ""
    Company: str = ""
    Title: str = "Manager"
    Seniority: str = "Manager"
    Industry: str = "Technology"
    NumberOfEmployees: int = 100
    LeadSource: str = "Web"
    Email_Opens_14d: int = 0
    Email_Clicks_14d: int = 0
    Web_Visits_14d: int = 0
    Pricing_Page_Visits: int = 0
    Form_Fills: int = 0
    Previous_Touches: int = 0
    Campaign_Responses: int = 0
    Days_Since_Last_Activity: int = 30
    Days_Since_Created: int = 10
    Has_Phone: int = 1
    Free_Email_Domain: int = 0
    Requested_Demo: int = 0


class Outcome(BaseModel):
    lead_id: str
    action: str
    result: str = Field(description="e.g. Meeting booked, No response, Not interested, Converted")
    score: int = 0


@app.get("/health")
def health():
    return {"status": "ok", "crm": "salesforce" if crm.live() else "mock", "features": len(MODEL["features"])}


@app.post("/score")
def score(lead: Lead):
    """Called by the Salesforce Flow / Apex for one lead. Returns the fields to write back."""
    return recommend.score_lead(MODEL, lead.model_dump())


@app.post("/score/batch")
def score_batch(leads: list[Lead]):
    return [{"Id": l.Id, **recommend.score_lead(MODEL, l.model_dump())} for l in leads]


@app.get("/api/leads")
def ranked_leads(limit: int = 200):
    """Pull open leads from the CRM, score them all, return ranked by score."""
    df = crm.fetch_open_leads()
    sc = recommend.score_frame(MODEL, df)
    out = pd.concat([df.reset_index(drop=True), sc.reset_index(drop=True)], axis=1).sort_values("AI_Score__c", ascending=False)
    return JSONResponse(out.head(limit).to_dict("records"))


@app.post("/api/rescore")
def rescore():
    """Score every open lead and write the AI fields back to the CRM (what the nightly batch job does)."""
    df = crm.fetch_open_leads(5000)
    sc = recommend.score_frame(MODEL, df)
    n = crm.write_scores(pd.concat([df[["Id"]].reset_index(drop=True), sc.reset_index(drop=True)], axis=1))
    return {"rescored": len(df), "written": n if isinstance(n, int) else len(df)}


@app.post("/api/leads/{lead_id}")
def edit_lead(lead_id: str, fields: dict):
    crm.update_lead(lead_id, fields)
    row = [r for r in crm.fetch_open_leads(5000).to_dict("records") if r["Id"] == lead_id]
    if not row:
        raise HTTPException(404, "Lead not found")
    return {**row[0], **recommend.score_lead(MODEL, row[0])}


@app.post("/api/outcome")
def outcome(o: Outcome):
    crm.log_outcome(o.lead_id, o.action, o.result, o.score)
    return {"recorded": True}


@app.get("/model.json")
def model_json():
    return FileResponse(ROOT / "models/model.json")


@app.get("/")
def home():
    return FileResponse(ROOT / "web/workbench.html")
