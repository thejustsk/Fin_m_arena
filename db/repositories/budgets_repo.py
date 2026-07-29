"""Budget persistence with recurring, selected-period, and special schedules."""
import uuid
from datetime import datetime

def _rows(rows): return [dict(r) for r in rows] if rows else []

class BudgetsRepo:
    def __init__(self, db): self.db=db
    def list_active(self, period_type=None):
        sql="SELECT * FROM budgets WHERE is_active=1"; p=[]
        if period_type: sql+=" AND COALESCE(period_type,'MONTHLY')=?"; p.append(period_type)
        return _rows(self.db.execute(sql+" ORDER BY created_at",p).fetchall())
    def list_inactive(self, period_type=None):
        sql="SELECT * FROM budgets WHERE is_active=0"; p=[]
        if period_type: sql+=" AND COALESCE(period_type,'MONTHLY')=?"; p.append(period_type)
        return _rows(self.db.execute(sql+" ORDER BY created_at DESC",p).fetchall())
    def exists(self, scope_type, scope_value, period_type, schedule_type='RECURRING', period_year=None, period_month=None, start_date=None, end_date=None, exclude_id=None):
        sql="SELECT 1 FROM budgets WHERE is_active=1 AND scope_type=? AND scope_value=? AND period_type=? AND COALESCE(schedule_type,'RECURRING')=?"; p=[scope_type,scope_value,period_type,schedule_type]
        if schedule_type=='SELECTED':
            sql+=" AND period_year=?"; p.append(period_year)
            if period_type=='MONTHLY': sql+=" AND period_month=?"; p.append(period_month)
        elif schedule_type=='SPECIAL':
            sql+=" AND start_date=? AND end_date=?"; p += [start_date,end_date]
        if exclude_id: sql+=" AND budget_id!=?"; p.append(exclude_id)
        return self.db.execute(sql,p).fetchone() is not None
    def create(self, scope_type, scope_value, limit_amount, alert_threshold_pct=80, period_type="MONTHLY", schedule_type="RECURRING", period_year=None, period_month=None, start_date=None, end_date=None):
        bid=str(uuid.uuid4())
        self.db.execute("INSERT INTO budgets(budget_id,scope_type,scope_value,limit_amount,alert_threshold_pct,is_active,created_at,period_type,schedule_type,period_year,period_month,start_date,end_date) VALUES(?,?,?,?,?,1,?,?,?,?,?,?,?)",(bid,scope_type,scope_value,float(limit_amount),float(alert_threshold_pct),datetime.now().isoformat(),period_type,schedule_type,period_year,period_month,start_date,end_date)); self.db.commit(); return bid
    def update(self,budget_id,scope_type,scope_value,limit_amount,alert_threshold_pct=80,**schedule):
        sets=['scope_type=?','scope_value=?','limit_amount=?','alert_threshold_pct=?']; vals=[scope_type,scope_value,float(limit_amount),float(alert_threshold_pct)]
        for key in ('period_type','schedule_type','period_year','period_month','start_date','end_date'):
            if key in schedule: sets.append(f'{key}=?'); vals.append(schedule[key])
        vals.append(budget_id); self.db.execute(f"UPDATE budgets SET {', '.join(sets)} WHERE budget_id=?",vals); self.db.commit()
    def deactivate(self,bid): self.db.execute("UPDATE budgets SET is_active=0 WHERE budget_id=?",(bid,)); self.db.commit()
    def reactivate(self,bid): self.db.execute("UPDATE budgets SET is_active=1 WHERE budget_id=?",(bid,)); self.db.commit()
    def delete(self,bid): self.db.execute("DELETE FROM budgets WHERE budget_id=?",(bid,)); self.db.commit()
