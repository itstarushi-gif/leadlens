"""Run:  python -m tests.test_all   (also works with pytest)"""
import json, subprocess, tempfile, os
import pandas as pd
from fastapi.testclient import TestClient
from src import model_io, recommend, crm
from src.generate_data import generate

ROOT = crm.ROOT
MODEL = model_io.load(ROOT / "models/model.json")


def test_bands():
    assert [recommend.priority(s) for s in (92, 81, 63, 28)] == ["Very High", "High", "Medium", "Low"]
    assert [recommend.action(s) for s in (92, 84, 72, 55, 30)] == ["Call the lead", "Schedule a demo", "Send personalized email", "Follow up later", "Put into nurture"]


def test_hot_lead_beats_cold_lead():
    hot = dict(Title="CEO", Seniority="C-Level", Industry="Technology", NumberOfEmployees=800, LeadSource="Referral", Email_Opens_14d=8,
               Email_Clicks_14d=5, Web_Visits_14d=12, Pricing_Page_Visits=4, Form_Fills=2, Previous_Touches=4, Campaign_Responses=2,
               Days_Since_Last_Activity=1, Days_Since_Created=10, Has_Phone=1, Free_Email_Domain=0, Requested_Demo=1)
    cold = dict(hot, Title="Analyst", Seniority="Individual", Industry="Education", NumberOfEmployees=5, LeadSource="Cold Outbound", Email_Opens_14d=0,
                Email_Clicks_14d=0, Web_Visits_14d=0, Pricing_Page_Visits=0, Form_Fills=0, Previous_Touches=0, Campaign_Responses=0,
                Days_Since_Last_Activity=70, Has_Phone=0, Free_Email_Domain=1, Requested_Demo=0)
    h, c = recommend.score_lead(MODEL, hot), recommend.score_lead(MODEL, cold)
    assert h["AI_Score__c"] >= 90 and h["Next_Best_Action__c"] == "Call the lead", h
    assert c["AI_Score__c"] < 20 and c["AI_Priority__c"] == "Low", c
    print("hot:", h["AI_Score__c"], h["Recommendation_Reason__c"]); print("cold:", c["AI_Score__c"], c["Recommendation_Reason__c"])


def test_no_phone_guardrail():
    lead = dict(Title="CEO", Seniority="C-Level", Industry="Technology", NumberOfEmployees=800, LeadSource="Referral", Email_Opens_14d=8,
                Email_Clicks_14d=5, Web_Visits_14d=12, Pricing_Page_Visits=4, Form_Fills=2, Previous_Touches=4, Campaign_Responses=2,
                Days_Since_Last_Activity=1, Days_Since_Created=10, Has_Phone=0, Free_Email_Domain=0, Requested_Demo=1)
    r = recommend.score_lead(MODEL, lead)
    assert r["Next_Best_Action__c"] == "Send personalized email" and "no phone" in r["Recommendation_Reason__c"]


def test_javascript_matches_python():
    df = pd.read_csv(ROOT / "data/crm_leads.csv").head(400)
    recs = df.to_dict("records")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(recs, fh); path = fh.name
    out = subprocess.run(["node", str(ROOT / "tests/parity.js"), str(ROOT / "web/workbench.html"), str(ROOT / "models/model.json"), path],
                         capture_output=True, text=True, check=True).stdout
    os.unlink(path)
    js = json.loads(out)
    bad = 0
    for r, j in zip(recs, js):
        p = recommend.score_lead(MODEL, r)
        for k in ("AI_Score__c", "AI_Priority__c", "Next_Best_Action__c", "Recommendation_Reason__c"):
            if p[k] != j[k]: bad += 1; print("MISMATCH", k, p[k], "|", j[k])
        assert abs(p["Conversion_Probability__c"] - round(j["p"], 4)) < 1e-9
    assert bad == 0
    print("JS and Python agree on all", len(recs), "leads")


def test_api_and_crm_loop():
    from api.main import app
    c = TestClient(app)
    assert c.get("/health").json()["status"] == "ok"
    body = {"Title": "VP Sales", "Seniority": "VP", "Pricing_Page_Visits": 3, "Requested_Demo": 1, "Email_Opens_14d": 6}
    r = c.post("/score", json=body).json()
    assert 0 <= r["AI_Score__c"] <= 100 and r["AI_Priority__c"] in ("Very High", "High", "Medium", "Low")
    leads = c.get("/api/leads?limit=50").json()
    assert len(leads) == 50 and leads[0]["AI_Score__c"] >= leads[-1]["AI_Score__c"]
    batch = c.post("/score/batch", json=[{"Id": "A"}, {"Id": "B", "Requested_Demo": 1}]).json()
    assert len(batch) == 2
    assert c.post("/api/outcome", json={"lead_id": leads[0]["Id"], "action": leads[0]["Next_Best_Action__c"], "result": "Meeting booked", "score": leads[0]["AI_Score__c"]}).json()["recorded"]
    lid = leads[-1]["Id"]
    before = leads[-1]["AI_Score__c"]
    after = c.post(f"/api/leads/{lid}", json={"Requested_Demo": 1, "Pricing_Page_Visits": 6, "Days_Since_Last_Activity": 0}).json()["AI_Score__c"]
    assert after > before, (before, after)
    print(f"update lead -> rescored: {before} -> {after}")
    assert c.post("/api/rescore").json()["rescored"] > 0
    assert "AI_Score__c" in pd.read_csv(crm.MOCK).columns


def _run_upload(csv_text, sdrs="SDR 1,SDR 2,SDR 3"):
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
        fh.write(csv_text); path = fh.name
    out = subprocess.run(["node", str(ROOT / "tests/upload.js"), str(ROOT / "web/workbench.html"), str(ROOT / "models/model.json"), path, sdrs],
                         capture_output=True, text=True, check=True).stdout
    os.unlink(path)
    return json.loads(out)


def test_csv_upload_scores_like_python_and_assigns_sdrs():
    df = pd.read_csv(ROOT / "data/crm_leads.csv").head(300)
    cols = ["Id", "Name", "Company", "Title", "Industry", "NumberOfEmployees", "LeadSource", "Email_Opens_14d", "Email_Clicks_14d", "Web_Visits_14d",
            "Pricing_Page_Visits", "Form_Fills", "Previous_Touches", "Campaign_Responses", "Days_Since_Last_Activity", "Days_Since_Created",
            "Has_Phone", "Free_Email_Domain", "Requested_Demo"]   # no Seniority column: it must be inferred from Title
    res = _run_upload(df[cols].to_csv(index=False))
    assert res["missing"] == [] and len(res["leads"]) == 300
    for r, j in zip(df.to_dict("records"), res["leads"]):
        p = recommend.score_lead(MODEL, r)
        assert (p["AI_Score__c"], p["Next_Best_Action__c"]) == (j["score"], j["action"]), (p["AI_Score__c"], j)
    sdr = pd.Series([j["sdr"] for j in res["leads"]])
    assert set(sdr) <= {"SDR 1", "SDR 2", "SDR 3", "Marketing nurture"}
    assert all(j["sdr"] == "Marketing nurture" for j in res["leads"] if j["action"] == "Put into nurture")
    counts = sdr[sdr != "Marketing nurture"].value_counts()
    assert counts.max() - counts.min() <= 2, counts
    print("upload parity OK; SDR workload:", counts.to_dict(), "| nurture:", int((sdr == "Marketing nurture").sum()))


def test_csv_upload_handles_messy_headers_and_values():
    csv = ('\ufeffFull Name;Account;Job Title;Employees;Phone;Email;Demo Requested;Pricing Views;Lead Source;Sector\n'
           '"Asha Rao";"Nova, Inc";"VP of Sales";"1,200";"+91 99999 99999";asha@nova.com;Yes;4;Partner Referral;Software\n'
           'Tom Lee;Blue Works;Analyst;8;;tom@gmail.com;No;0;Cold Call;School\n')
    res = _run_upload(csv, "Ravi,Meera")
    a, b = res["leads"]
    assert a["Seniority"] == "VP" and b["Seniority"] == "Individual"
    assert a["score"] > b["score"] and a["sdr"] in ("Ravi", "Meera")
    assert "Email Opens 14d" in res["missing"]
    print("messy CSV OK:", a["score"], a["action"], "|", b["score"], b["action"])


if __name__ == "__main__":
    import shutil
    backup = crm.MOCK.with_suffix(".bak"); shutil.copy(crm.MOCK, backup)
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_"): fn(); print("PASS", name)
    finally:
        shutil.move(backup, crm.MOCK)
        if crm.OUTCOMES.exists(): crm.OUTCOMES.unlink()
