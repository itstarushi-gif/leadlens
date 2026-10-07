// Re-scores a lead whenever it is created or a scoring input changes.
trigger LeadAiTrigger on Lead (after insert, after update) {
    Set<Id> ids = new Set<Id>();
    for (Lead l : Trigger.new) {
        if (Trigger.isInsert) { ids.add(l.Id); continue; }
        Lead o = Trigger.oldMap.get(l.Id);
        if (l.Email_Opens_14d__c != o.Email_Opens_14d__c || l.Pricing_Page_Visits__c != o.Pricing_Page_Visits__c ||
            l.Requested_Demo__c != o.Requested_Demo__c || l.Web_Visits_14d__c != o.Web_Visits_14d__c ||
            l.Days_Since_Last_Activity__c != o.Days_Since_Last_Activity__c || l.Title != o.Title) ids.add(l.Id);
    }
    if (!ids.isEmpty() && !System.isQueueable() && !System.isBatch()) System.enqueueJob(new LeadScoringService.ScoreJob(ids));
}
