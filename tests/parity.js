// Runs the browser scoring engine in Node on leads from stdin and prints results as JSON.
const fs=require("fs");
const html=fs.readFileSync(process.argv[2],"utf8");
const eng=html.split("/* ---- scoring engine")[1].split("/* ---- UI ----")[0].split("\n").slice(1).join("\n");
const SEN=["Individual","Manager","Director","VP","C-Level"],INDS=["Technology","Finance","Healthcare","Manufacturing","Retail","Education","Other"],SRCS=["Web","Referral","Event","Paid Ad","Partner","Cold Outbound"];
const RAW={email_opens:"Email_Opens_14d",email_clicks:"Email_Clicks_14d",web_visits:"Web_Visits_14d",pricing_visits:"Pricing_Page_Visits",form_fills:"Form_Fills",previous_touches:"Previous_Touches",campaign_responses:"Campaign_Responses",days_since_activity:"Days_Since_Last_Activity",days_since_created:"Days_Since_Created",has_phone:"Has_Phone",free_email:"Free_Email_Domain",requested_demo:"Requested_Demo"};
const M=JSON.parse(fs.readFileSync(process.argv[3],"utf8"));
const leads=JSON.parse(fs.readFileSync(process.argv[4],"utf8"));
const f=new Function("M","SEN","INDS","SRCS","RAW","leads",eng+";return leads.map(l=>{const s=score(l);return {AI_Score__c:s.score,AI_Priority__c:s.priority,Next_Best_Action__c:s.action,Recommendation_Reason__c:s.reason,p:s.prob}})");
console.log(JSON.stringify(f(M,SEN,INDS,SRCS,RAW,leads)));
