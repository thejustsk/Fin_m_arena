"""Budget calculations for recurring, selected-period and special schedules."""
from services.nw_constants import NW_NEED, NW_WANT

class BudgetService:
 def __init__(self,budgets_repo,tx_repo): self.budget_repo,self.tx_repo=budgets_repo,tx_repo
 def check_budgets(self,y,m=None,period_type='MONTHLY',start_date=None,end_date=None):
  if period_type=='SPECIAL': txns=self.tx_repo.list_filters(date_from=start_date,date_to=end_date,limit=50000)
  elif period_type=='YEARLY': txns=self.tx_repo.list_filters(date_from=f'{y:04d}-01-01',date_to=f'{y:04d}-12-31',limit=50000)
  else: txns=self.tx_repo.get_monthly(y,m)
  rows=[]; candidates=[]
  for b in self.budget_repo.list_active(period_type):
   mode=b.get('schedule_type') or 'RECURRING'
   if period_type=='MONTHLY' and mode=='SELECTED' and (b.get('period_year')!=y or b.get('period_month')!=m): continue
   if period_type=='YEARLY' and mode=='SELECTED' and b.get('period_year')!=y: continue
   if period_type=='SPECIAL' and not (b.get('start_date')==start_date and b.get('end_date')==end_date): continue
   candidates.append(b)
  # A selected-period budget overrides the matching recurring target.
  overrides={(b['scope_type'],b['scope_value']) for b in candidates if (b.get('schedule_type') or 'RECURRING') in ('SELECTED','SPECIAL')}
  for b in candidates:
   mode=b.get('schedule_type') or 'RECURRING'
   if mode=='RECURRING' and (b['scope_type'],b['scope_value']) in overrides: continue
   if b['scope_type']=='CATEGORY': matched=[t for t in txns if t.get('category')==b['scope_value']]
   elif b['scope_type']=='PF_CATEGORY': matched=[t for t in txns if t.get('pf_category')==b['scope_value']]
   elif b['scope_type']=='NEED_WANT': matched=[t for t in txns if t.get('neednwant')==(NW_NEED if b['scope_value']=='NEED' else NW_WANT)]
   elif b['scope_type']=='TRANSACTION_GROUP': matched=[t for t in txns if t.get('transaction_kind','REGULAR')==b['scope_value']]
   else: matched=[t for t in txns if t.get('tx_type')=='DEBIT' and t.get('transaction_kind','REGULAR')=='REGULAR']
   spent=sum(t.get('amount') or 0 for t in matched); limit=b['limit_amount'] or 0
   rows.append({**b,'spent':spent,'pct':spent/limit*100 if limit else 0,'remaining':limit-spent})
  return rows
