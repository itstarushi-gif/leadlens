import { LightningElement, api, wire } from 'lwc';
import { getRecord, getFieldValue } from 'lightning/uiRecordApi';
import SCORE from '@salesforce/schema/Lead.AI_Score__c';
import PROB from '@salesforce/schema/Lead.Conversion_Probability__c';
import PRIORITY from '@salesforce/schema/Lead.AI_Priority__c';
import ACTION from '@salesforce/schema/Lead.Next_Best_Action__c';
import REASON from '@salesforce/schema/Lead.Recommendation_Reason__c';

export default class LeadAiPanel extends LightningElement {
  @api recordId;
  @wire(getRecord, { recordId: '$recordId', fields: [SCORE, PROB, PRIORITY, ACTION, REASON] }) lead;
  get score() { return getFieldValue(this.lead.data, SCORE); }
  get probability() { return getFieldValue(this.lead.data, PROB); }
  get priority() { return getFieldValue(this.lead.data, PRIORITY); }
  get action() { return getFieldValue(this.lead.data, ACTION); }
  get reason() { return getFieldValue(this.lead.data, REASON); }
}
