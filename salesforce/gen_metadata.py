"""Generates the Salesforce DX metadata (custom Lead fields) so the project can be deployed with:  sf project deploy start"""
from pathlib import Path
base = Path(__file__).parent / "force-app/main/default/objects/Lead/fields"
base.mkdir(parents=True, exist_ok=True)
NS = 'xmlns="http://soap.sforce.com/2006/04/metadata"'

def num(api, label, scale=0, desc=""):
    return api, f'<type>Number</type><precision>18</precision><scale>{scale}</scale>', label, desc
def pct(api, label, desc=""):
    return api, '<type>Percent</type><precision>5</precision><scale>1</scale>', label, desc
def txt(api, label, ln=255, desc=""):
    return api, f'<type>Text</type><length>{ln}</length>', label, desc
def chk(api, label, desc=""):
    return api, '<type>Checkbox</type><defaultValue>false</defaultValue>', label, desc

vals = lambda vs: "<type>Picklist</type><valueSet><restricted>true</restricted><valueSetDefinition><sorted>false</sorted>" + "".join(f"<value><fullName>{v}</fullName><default>false</default><label>{v}</label></value>" for v in vs) + "</valueSetDefinition></valueSet>"
fields = [
 # engagement inputs (normally synced from Marketing Cloud / Pardot / website tracking)
 ("Seniority__c", vals(["Individual", "Manager", "Director", "VP", "C-Level"]), "Seniority", "Derived from Title"),
 num("Email_Opens_14d__c", "Email Opens 14d"), num("Email_Clicks_14d__c", "Email Clicks 14d"), num("Web_Visits_14d__c", "Web Visits 14d"),
 num("Pricing_Page_Visits__c", "Pricing Page Visits"), num("Form_Fills__c", "Form Fills"), num("Previous_Touches__c", "Previous Touches"),
 num("Campaign_Responses__c", "Campaign Responses"), num("Days_Since_Last_Activity__c", "Days Since Last Activity"),
 num("Days_Since_Created__c", "Days Since Created"), chk("Has_Phone__c", "Has Phone"), chk("Free_Email_Domain__c", "Free Email Domain"),
 chk("Requested_Demo__c", "Requested Demo"),
 # AI outputs written by LeadLens
 num("AI_Score__c", "AI Lead Score", 0, "0-100 lead score from the LeadLens model"),
 pct("Conversion_Probability__c", "Conversion Probability"),
 ("AI_Priority__c", vals(["Very High", "High", "Medium", "Low"]), "AI Priority", ""),
 txt("Next_Best_Action__c", "Next Best Action"), txt("Recommendation_Reason__c", "Recommendation Reason"),
 ("AI_Scored_At__c", "<type>DateTime</type>", "AI Scored At", ""),
]
for api, body, label, desc in fields:
    (base / f"{api}.field-meta.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<CustomField {NS}>\n  <fullName>{api}</fullName>\n  <label>{label}</label>\n'
        f'  <description>{desc}</description>\n  <required>false</required>\n  <trackTrending>false</trackTrending>\n  {body}\n</CustomField>\n')
print(len(fields), "field files written to", base)
