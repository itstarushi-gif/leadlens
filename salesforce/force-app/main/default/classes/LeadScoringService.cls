/**
 * Calls the LeadLens scoring API and writes the AI fields back onto the Lead.
 * Needs a Named Credential called LeadLens_API pointing at your deployed API (see README).
 * Can be used from a Flow (Action: "Score Lead with LeadLens") or from the trigger below.
 */
public with sharing class LeadScoringService {

    public class Request { @InvocableVariable(required=true) public Id leadId; }

    @InvocableMethod(label='Score Lead with LeadLens' description='Scores a lead and updates AI fields')
    public static void scoreFromFlow(List<Request> reqs) {
        Set<Id> ids = new Set<Id>();
        for (Request r : reqs) ids.add(r.leadId);
        System.enqueueJob(new ScoreJob(ids));
    }

    public class ScoreJob implements Queueable, Database.AllowsCallouts {
        Set<Id> ids;
        public ScoreJob(Set<Id> ids) { this.ids = ids; }
        public void execute(QueueableContext qc) {
            List<Lead> updates = new List<Lead>();
            for (Lead l : [SELECT Id, Title, Seniority__c, Industry, NumberOfEmployees, LeadSource, Email_Opens_14d__c,
                                  Email_Clicks_14d__c, Web_Visits_14d__c, Pricing_Page_Visits__c, Form_Fills__c,
                                  Previous_Touches__c, Campaign_Responses__c, Days_Since_Last_Activity__c,
                                  Days_Since_Created__c, Has_Phone__c, Free_Email_Domain__c, Requested_Demo__c
                           FROM Lead WHERE Id IN :ids]) {
                Map<String, Object> body = new Map<String, Object>{
                    'Id' => l.Id, 'Title' => l.Title, 'Seniority' => l.Seniority__c, 'Industry' => l.Industry,
                    'NumberOfEmployees' => l.NumberOfEmployees == null ? 1 : l.NumberOfEmployees, 'LeadSource' => l.LeadSource,
                    'Email_Opens_14d' => nz(l.Email_Opens_14d__c), 'Email_Clicks_14d' => nz(l.Email_Clicks_14d__c),
                    'Web_Visits_14d' => nz(l.Web_Visits_14d__c), 'Pricing_Page_Visits' => nz(l.Pricing_Page_Visits__c),
                    'Form_Fills' => nz(l.Form_Fills__c), 'Previous_Touches' => nz(l.Previous_Touches__c),
                    'Campaign_Responses' => nz(l.Campaign_Responses__c), 'Days_Since_Last_Activity' => nz(l.Days_Since_Last_Activity__c),
                    'Days_Since_Created' => nz(l.Days_Since_Created__c), 'Has_Phone' => l.Has_Phone__c ? 1 : 0,
                    'Free_Email_Domain' => l.Free_Email_Domain__c ? 1 : 0, 'Requested_Demo' => l.Requested_Demo__c ? 1 : 0 };
                HttpRequest req = new HttpRequest();
                req.setEndpoint('callout:LeadLens_API/score');
                req.setMethod('POST');
                req.setHeader('Content-Type', 'application/json');
                req.setBody(JSON.serialize(body));
                HttpResponse res = new Http().send(req);
                if (res.getStatusCode() == 200) {
                    Map<String, Object> r = (Map<String, Object>) JSON.deserializeUntyped(res.getBody());
                    updates.add(new Lead(Id = l.Id,
                        AI_Score__c = (Decimal) r.get('AI_Score__c'),
                        Conversion_Probability__c = ((Decimal) r.get('Conversion_Probability__c')) * 100,
                        AI_Priority__c = (String) r.get('AI_Priority__c'),
                        Next_Best_Action__c = (String) r.get('Next_Best_Action__c'),
                        Recommendation_Reason__c = ((String) r.get('Recommendation_Reason__c')).left(255),
                        AI_Scored_At__c = System.now()));
                }
            }
            if (!updates.isEmpty()) update updates;
        }
        private Decimal nz(Decimal d) { return d == null ? 0 : d; }
    }
}
