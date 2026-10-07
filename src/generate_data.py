"""Generate a realistic synthetic Salesforce Lead dataset (Lead object + engagement signals).

Real CRM data is private, so we simulate it. A hidden "buyer interest" variable drives
both the engagement signals the CRM can see and the chance of conversion, plus noise,
so the model has to learn from imperfect proxies, as in real life.
"""
import numpy as np, pandas as pd
from pathlib import Path

INDUSTRIES = ["Technology", "Finance", "Healthcare", "Manufacturing", "Retail", "Education", "Other"]
SOURCES = ["Web", "Referral", "Event", "Paid Ad", "Partner", "Cold Outbound"]
SENIORITY = ["Individual", "Manager", "Director", "VP", "C-Level"]
TITLES = {"Individual": ["Analyst", "Engineer", "Coordinator"], "Manager": ["Sales Manager", "IT Manager", "Ops Manager"],
          "Director": ["Director of Sales", "Director of IT", "Head of Ops"], "VP": ["VP Sales", "VP Engineering", "VP Marketing"],
          "C-Level": ["CEO", "CTO", "COO", "CFO"]}
FIRST = ["Aarav", "Priya", "Rohan", "Ananya", "Vikram", "Neha", "Arjun", "Isha", "Karan", "Meera", "Sanjay", "Divya", "Rahul", "Pooja", "Amit", "Sneha", "Nikhil", "Kavya", "Dev", "Riya"]
LAST = ["Sharma", "Verma", "Patel", "Iyer", "Singh", "Gupta", "Reddy", "Nair", "Mehta", "Joshi", "Kapoor", "Das", "Rao", "Khan", "Malhotra", "Bose"]
COMP_A = ["Nova", "Apex", "Blue", "Zen", "Quanta", "Orbit", "Vertex", "Pioneer", "Summit", "Lumen", "Cobalt", "Helix"]
COMP_B = ["Systems", "Labs", "Industries", "Solutions", "Dynamics", "Group", "Networks", "Partners", "Works", "Health"]

IND_W = {"Technology": .5, "Finance": .4, "Healthcare": .2, "Manufacturing": 0, "Retail": -.2, "Education": -.4, "Other": -.3}
SRC_W = {"Web": 0, "Referral": 1.0, "Event": .5, "Paid Ad": -.2, "Partner": .4, "Cold Outbound": -.7}


def generate(n=6000, seed=42, target_rate=0.33):
    r = np.random.default_rng(seed)
    interest = r.normal(0, 1, n)  # hidden buyer interest
    sen = r.choice(5, n, p=[.3, .3, .2, .12, .08])
    emp = np.exp(r.normal(4.6, 1.5, n)).clip(2, 50000).astype(int)
    ind = r.choice(INDUSTRIES, n, p=[.24, .14, .12, .14, .14, .1, .12])
    src = r.choice(SOURCES, n, p=[.28, .1, .14, .22, .08, .18])
    pois = lambda base, k: r.poisson(np.exp(base + k * interest).clip(0, 12))
    opens = pois(.9, .5).clip(0, 15)
    clicks = np.minimum(pois(-.1, .6), opens + 1)
    visits = pois(.8, .55).clip(0, 25)
    pricing = np.minimum(pois(-.8, .7), visits)
    forms = np.minimum(pois(-1.2, .6), 4)
    demo = (r.random(n) < 1 / (1 + np.exp(-(-3.0 + 1.4 * interest + .2 * sen)))).astype(int)
    touches = pois(.2, .3).clip(0, 12)
    camp = np.minimum(pois(-.3, .4), 6)
    days_last = (np.exp(r.normal(2.2, .9, n) - .35 * interest)).clip(0, 90).astype(int)
    days_created = r.integers(1, 120, n)
    has_phone = (r.random(n) < .7).astype(int)
    free_email = (r.random(n) < np.where(sen >= 2, .06, .25)).astype(int)

    z = (.55 * sen + .32 * (np.log(emp) - 4.6) + .13 * opens + .18 * clicks + .05 * visits + .32 * pricing
         + .3 * forms + 1.5 * demo + .1 * touches + .12 * camp - .035 * days_last + .3 * has_phone - .9 * free_email
         + np.array([IND_W[i] for i in ind]) + np.array([SRC_W[s] for s in src])
         + .35 * ((pricing >= 2) & (sen >= 2)) + 0.9 * interest + r.normal(0, .9, n))
    lo, hi = -15, 15
    for _ in range(50):  # find intercept giving the target conversion rate
        mid = (lo + hi) / 2
        p = (1 / (1 + np.exp(-(z + mid)))).mean()
        lo, hi = (mid, hi) if p < target_rate else (lo, mid)
    converted = (r.random(n) < 1 / (1 + np.exp(-(z + mid)))).astype(int)

    names = [f"{r.choice(FIRST)} {r.choice(LAST)}" for _ in range(n)]
    comps = [f"{r.choice(COMP_A)}{r.choice(COMP_B)}" for _ in range(n)]
    df = pd.DataFrame({
        "Id": [f"00Q{i:012d}" for i in range(n)], "Name": names, "Company": comps,
        "Title": [r.choice(TITLES[SENIORITY[s]]) for s in sen], "Seniority": [SENIORITY[s] for s in sen],
        "Industry": ind, "NumberOfEmployees": emp, "LeadSource": src,
        "Email_Opens_14d": opens, "Email_Clicks_14d": clicks, "Web_Visits_14d": visits,
        "Pricing_Page_Visits": pricing, "Form_Fills": forms, "Previous_Touches": touches,
        "Campaign_Responses": camp, "Days_Since_Last_Activity": days_last, "Days_Since_Created": days_created,
        "Has_Phone": has_phone, "Free_Email_Domain": free_email, "Requested_Demo": demo,
        "Converted": converted})
    return df


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "data"
    out.mkdir(exist_ok=True)
    df = generate()
    df.to_csv(out / "leads_history.csv", index=False)
    print(df.shape, "conversion rate:", round(df.Converted.mean(), 3))
