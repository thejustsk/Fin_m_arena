"""Derived personal Split spending for analytics.

A Split ledger transaction may represent the full group payment. Analytics must
use only the self contact's allocated share, never the full paid amount.
"""
def personal_share_rows(db, date_from=None, date_to=None):
    sql=("SELECT e.expense_id,e.expense_date,e.category,e.pf_category,e.neednwant,"
         "e.description,s.share_amount FROM split_expenses e "
         "JOIN split_shares s ON s.expense_id=e.expense_id "
         "JOIN split_contacts c ON c.contact_id=s.contact_id WHERE c.is_self=1")
    params=[]
    if date_from: sql+=' AND e.expense_date>=?'; params.append(date_from)
    if date_to: sql+=' AND e.expense_date<=?'; params.append(date_to)
    rows=db.execute(sql,params).fetchall()
    return [dict(id=f"split-share-{r['expense_id']}",tx_date=r['expense_date'],tx_type='DEBIT',amount=r['share_amount'],category=r['category'],pf_category=r['pf_category'],neednwant=r['neednwant'],transaction_kind='SPLIT_PERSONAL_SHARE',description=r['description'],split_personal_share=True) for r in rows]
