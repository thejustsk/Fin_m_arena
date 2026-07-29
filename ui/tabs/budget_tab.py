"""Monthly recurring budgets — set once, evaluated every calendar month."""
from datetime import date, timedelta
from PyQt5.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
                             QFrame,QScrollArea,QDialog,QFormLayout,QComboBox,
                             QDoubleSpinBox,QDialogButtonBox,QSpinBox,QMessageBox,QDateEdit)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QCursor
from ui.theme import C
from ui.sidebar import fmt_money
from services.budget_service import BudgetService
from ui.widgets.empty_state import EmptyState
from ui.widgets.toast import Toast
from ui.tabs.database_tab import _tx_card, _day_header


class BudgetTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db, self.repos, self.services = db, repos, services
        self.repo = repos["budgets"]
        self.lookups = repos["lookups"]
        self.engine = BudgetService(self.repo, repos["transactions"])
        self.period_type = "MONTHLY"
        self._build()

    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(32,24,32,24); root.setSpacing(12)
        row=QHBoxLayout(); title_col=QVBoxLayout(); title_col.setSpacing(2)
        self.title=QLabel("📊  Monthly Budgets"); self.title.setStyleSheet(f"font-size:22px;font-weight:800;color:{C['text']};")
        self.sub=QLabel("Set a limit once — it automatically applies every calendar month."); self.sub.setStyleSheet(f"font-size:12px;color:{C['text3']};")
        title_col.addWidget(self.title); title_col.addWidget(self.sub); row.addLayout(title_col); row.addStretch()
        self.add=QPushButton("＋ Add Monthly Budget"); self.add.setObjectName("primary"); self.add.setCursor(QCursor(Qt.PointingHandCursor)); self.add.clicked.connect(self._open_editor); row.addWidget(self.add)
        root.addLayout(row)
        periods=QHBoxLayout(); periods.setSpacing(8)
        self.month_btn=QPushButton("Monthly"); self.year_btn=QPushButton("Yearly"); self.special_btn=QPushButton("Special")
        self.month_btn.clicked.connect(lambda:self._set_period("MONTHLY")); self.year_btn.clicked.connect(lambda:self._set_period("YEARLY")); self.special_btn.clicked.connect(lambda:self._set_period("SPECIAL"))
        periods.addWidget(self.month_btn); periods.addWidget(self.year_btn); periods.addWidget(self.special_btn)
        self.month_pick=QComboBox(); [self.month_pick.addItem(date(2026,m,1).strftime('%b'),m) for m in range(1,13)]
        self.month_pick.setCurrentIndex(date.today().month-1)
        self.year_pick=QSpinBox(); self.year_pick.setRange(2020,2035); self.year_pick.setValue(date.today().year)
        self.month_pick.currentIndexChanged.connect(self.refresh); self.year_pick.valueChanged.connect(self.refresh)
        self.special_start=QDateEdit(QDate.currentDate()); self.special_start.setCalendarPopup(True)
        self.special_end=QDateEdit(QDate.currentDate().addDays(30)); self.special_end.setCalendarPopup(True)
        self.special_start.dateChanged.connect(self.refresh); self.special_end.dateChanged.connect(self.refresh)
        periods.addWidget(self.month_pick); periods.addWidget(self.year_pick); periods.addWidget(self.special_start); periods.addWidget(self.special_end)
        periods.addStretch()
        self.inactive_btn=QPushButton('Inactive Budgets'); self.inactive_btn.clicked.connect(self._show_inactive); periods.addWidget(self.inactive_btn)
        root.addLayout(periods)
        self.kpi_row=QHBoxLayout(); self.kpi_row.setSpacing(10); root.addLayout(self.kpi_row)
        self.summary=QLabel(); self.summary.setStyleSheet(f"color:{C['text3']};font-size:12px;font-weight:600;"); root.addWidget(self.summary)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame); scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner=QWidget(); inner.setStyleSheet("background:transparent;"); self.lay=QVBoxLayout(inner); self.lay.setSpacing(10); self.lay.setAlignment(Qt.AlignTop); scroll.setWidget(inner)
        content=QHBoxLayout(); content.addWidget(scroll,3)
        panel=QFrame(); panel.setMinimumWidth(260); panel.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        pl=QVBoxLayout(panel); pl.setContentsMargins(14,12,14,12); title=QLabel('🔔 Budget Warnings'); title.setStyleSheet(f"font-size:14px;font-weight:800;color:{C['text']};"); pl.addWidget(title)
        self.warn_lay=QVBoxLayout(); self.warn_lay.setSpacing(8); pl.addLayout(self.warn_lay); pl.addStretch(); content.addWidget(panel,1); root.addLayout(content,1)

    def on_activated(self): self.refresh()
    def _set_period(self, period):
        self.period_type=period; self.refresh()
    def refresh(self):
        active=f"background:{C['accent']};color:{C['on_accent']};border:none;"
        inactive=f"background:{C['surface']};color:{C['text2']};border:1px solid {C['border']};"
        for btn,period in ((self.month_btn,'MONTHLY'),(self.year_btn,'YEARLY'),(self.special_btn,'SPECIAL')):
            btn.setStyleSheet(f"QPushButton{{{active if self.period_type==period else inactive}border-radius:8px;padding:7px 16px;font-weight:700;}}")
        is_year=self.period_type=='YEARLY'; is_special=self.period_type=='SPECIAL'
        self.title.setText('📊  Special Budgets' if is_special else ('📊  Yearly Budgets' if is_year else '📊  Monthly Budgets'))
        self.sub.setText('One-time budgets for a selected date range — never recurring.' if is_special else ('Set a limit once — it automatically applies every calendar year.' if is_year else 'Set a limit once — it automatically applies every calendar month.'))
        self.add.setText('＋ Add Special Budget' if is_special else ('＋ Add Yearly Budget' if is_year else '＋ Add Monthly Budget'))
        # Special page filters by year only; exact dates belong inside the
        # Special Budget editor.
        self.month_pick.setVisible(self.period_type=='MONTHLY'); self.special_start.hide(); self.special_end.hide()
        while self.lay.count():
            it=self.lay.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        while self.kpi_row.count():
            it=self.kpi_row.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        year=self.year_pick.value(); month=self.month_pick.currentData()
        start=self.special_start.date().toString('yyyy-MM-dd'); end=self.special_end.date().toString('yyyy-MM-dd')
        budgets=self.engine.check_budgets(year,month,self.period_type,start,end)
        total_limit=sum(b['limit_amount'] for b in budgets); total_spent=sum(b['spent'] for b in budgets)
        while self.warn_lay.count():
            it=self.warn_lay.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        today=date.today(); warning_budgets=[]
        warning_budgets += self.engine.check_budgets(today.year,today.month,'MONTHLY')
        warning_budgets += self.engine.check_budgets(today.year,today.month,'YEARLY')
        special_current = self.engine.check_budgets(today.year,today.month,'SPECIAL')
        month_start=today.replace(day=1).isoformat()
        month_end=(today.replace(day=28)+timedelta(days=4)).replace(day=1)-timedelta(days=1)
        warning_budgets += [b for b in special_current if (b.get('start_date') or '') <= month_end.isoformat() and (b.get('end_date') or '') >= month_start]
        flagged=[b for b in warning_budgets if b['pct']>=b['alert_threshold_pct']]
        if not flagged:
            ok=QLabel('✓ No budget warnings for the current month/year.'); ok.setWordWrap(True); ok.setStyleSheet(f"font-size:11px;color:{C['green']};font-weight:600;"); self.warn_lay.addWidget(ok)
        for b in flagged:
            col=C['red'] if b['pct']>=100 else C['amber']; ptype=b.get('period_type','MONTHLY')
            period_name={'MONTHLY':'Monthly','YEARLY':'Yearly','SPECIAL':'Special'}.get(ptype,'Monthly')
            detail=(f"{b.get('start_date')} → {b.get('end_date')}" if ptype=='SPECIAL' else (today.strftime('%B %Y') if ptype=='MONTHLY' else str(today.year)))
            balance_text=(f"Over budget by {fmt_money(abs(b['remaining']))}" if b['remaining']<0 else f"{fmt_money(b['remaining'])} remaining")
            text=QLabel(f"{period_name} · {self._name(b)}\n{detail} · {b['pct']:.0f}% used · {balance_text}")
            text.setWordWrap(True); text.setStyleSheet(f"background:{C['red_bg'] if b['pct']>=100 else C['amber_bg']};color:{col};border:1px solid {col};border-radius:8px;padding:8px;font-size:11px;font-weight:700;"); self.warn_lay.addWidget(text)
        warning=sum(1 for b in budgets if b['pct']>=b['alert_threshold_pct'] and b['pct']<100)
        exceeded=sum(1 for b in budgets if b['pct']>=100)
        net_remaining=total_limit-total_spent
        rem_label='Remaining' if net_remaining>=0 else 'Over Budget'
        rem_value=fmt_money(net_remaining) if net_remaining>=0 else fmt_money(abs(net_remaining))
        for label,value,color in [('Active',str(len(budgets)),C['accent']),('Warning',str(warning),C['amber']),('Exceeded',str(exceeded),C['red']),(rem_label,rem_value,C['green'] if net_remaining>=0 else C['red'])]:
            w=QFrame(); w.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:10px;}}QLabel{{background:transparent;border:none;}}")
            l=QVBoxLayout(w); l.setContentsMargins(12,8,12,8); l.addWidget(QLabel(value)); l.itemAt(0).widget().setStyleSheet(f"font-size:16px;font-weight:800;color:{color};")
            lab=QLabel(label); lab.setStyleSheet(f"font-size:10px;font-weight:700;color:{C['text3']};"); l.addWidget(lab); self.kpi_row.addWidget(w)
        period_label=(str(year) if self.period_type in ('SPECIAL','YEARLY') else date(year,month,1).strftime('%B %Y'))
        self.summary.setText(f"{period_label} · {len(budgets)} active budget{'s' if len(budgets)!=1 else ''} · {fmt_money(total_spent)} used of {fmt_money(total_limit)}")
        if not budgets:
            if self.period_type=='SPECIAL':
                title='No Special Budgets for this year'; hint='Create a one-time budget for any custom date range that overlaps this year.'; action='＋ Add Special Budget'
            elif self.period_type=='YEARLY':
                title='No Yearly Budgets yet'; hint='Create a recurring or selected-year budget for this calendar year.'; action='＋ Add Yearly Budget'
            else:
                title='No Monthly Budgets yet'; hint='Create a recurring or selected-month budget for this calendar month.'; action='＋ Add Monthly Budget'
            self.lay.addWidget(EmptyState('📊',title,hint,action,self._open_editor)); self.lay.addStretch(); return
        for b in budgets: self.lay.addWidget(self._card(b))
        self.lay.addStretch()

    def _name(self,b):
        if b['scope_type']=='TOTAL_EXPENSE': return 'Total Personal Spending'
        if b['scope_type']=='NEED_WANT': return 'Want Spending'
        for c in self.lookups.list_categories():
            if c['category_id']==b['scope_value']: return c['display_name']
        return b['scope_value']

    def _card(self,b):
        pct=b['pct']; color=C['green'] if pct<80 else (C['amber'] if pct<100 else C['red'])
        card=QFrame(); card.setCursor(QCursor(Qt.PointingHandCursor)); card.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-left:4px solid {color};border-radius:10px;}}QLabel{{background:transparent;border:none;}}")
        lay=QVBoxLayout(card); lay.setContentsMargins(16,12,16,12); lay.setSpacing(7)
        top=QHBoxLayout(); name=QLabel(self._name(b)); name.setStyleSheet(f"font-size:15px;font-weight:800;color:{C['text']};"); top.addWidget(name); top.addStretch()
        edit=QPushButton("Edit"); edit.setCursor(QCursor(Qt.PointingHandCursor)); edit.clicked.connect(lambda: self._open_editor(b)); top.addWidget(edit)
        off=QPushButton("Deactivate"); off.setCursor(QCursor(Qt.PointingHandCursor)); off.clicked.connect(lambda: self._deactivate_budget(b)); top.addWidget(off)
        delete=QPushButton("Delete"); delete.setCursor(QCursor(Qt.PointingHandCursor)); delete.clicked.connect(lambda: self._delete_budget(b)); top.addWidget(delete); lay.addLayout(top)
        value=QLabel(f"{fmt_money(b['spent'])} of {fmt_money(b['limit_amount'])}  ·  {pct:.0f}% used"); value.setStyleSheet(f"font-size:14px;font-weight:800;color:{color};"); lay.addWidget(value)
        bar=QFrame(); bar.setFixedHeight(8); bar.setStyleSheet(f"background:{C['border2']};border-radius:4px;"); bl=QHBoxLayout(bar); bl.setContentsMargins(0,0,0,0); bl.setSpacing(0); fill=QFrame(); fill.setStyleSheet(f"background:{color};border-radius:4px;"); bl.addWidget(fill,max(1,min(100,int(pct)))); bl.addStretch(max(1,100-min(100,int(pct)))); lay.addWidget(bar)
        remaining='over budget by '+fmt_money(abs(b['remaining'])) if b['remaining']<0 else fmt_money(b['remaining'])+' remaining'
        cap=QLabel(f"Alert at {b['alert_threshold_pct']:.0f}% · {remaining}"); cap.setStyleSheet(f"font-size:11px;color:{C['text3']};"); lay.addWidget(cap)
        if self.period_type=='YEARLY':
            today=date.today(); expected=(today.timetuple().tm_yday / (366 if today.year%4==0 else 365))*100
            pace='ahead of plan' if pct > expected + 5 else ('behind plan' if pct < expected - 5 else 'on pace')
            pace_lbl=QLabel(f"Year progress {expected:.0f}% · spending {pct:.0f}% · {pace}")
            pace_lbl.setStyleSheet(f"font-size:11px;color:{C['text3']};font-weight:600;"); lay.addWidget(pace_lbl)
        # Inline, expandable transaction drill-down. Initial batch is small;
        # more dated groups/cards render only while scrolling inside the card.
        details=QScrollArea(); details.setWidgetResizable(True); details.setFrameShape(QFrame.NoFrame)
        # Use the available Budget-list column height when expanded so several
        # dated transaction cards are visible, not just a single row.
        details.setMinimumHeight(480); details.setMaximumHeight(680); details.hide()
        inner=QWidget(); detail_lay=QVBoxLayout(inner); detail_lay.setSpacing(6); details.setWidget(inner)
        card._budget_expanded=False
        def toggle_details(event=None, budget=b, target=details, dl=detail_lay, host=card):
            if host._budget_expanded:
                target.hide(); host._budget_expanded=False; return
            host._budget_expanded=True; target.show()
            if getattr(host,'_budget_loaded',False): return
            host._budget_loaded=True
            txns=sorted(self.engine.transactions_for(budget,self.year_pick.value(),self.month_pick.currentData()),key=lambda t:t.get('tx_date',''),reverse=True)
            pending=list(txns); batch_size=10; last_date=None
            def append_batch():
                nonlocal pending,last_date
                batch,pending=pending[:batch_size],pending[batch_size:]
                for tx in batch:
                    if tx.get('tx_date')!=last_date:
                        last_date=tx.get('tx_date')
                        try: dl.addWidget(_day_header(date.fromisoformat(last_date).strftime('%A, %d %b')))
                        except Exception: dl.addWidget(_day_header(last_date))
                    dl.addWidget(_tx_card(tx))
                if not pending: dl.addStretch()
            append_batch()
            details.verticalScrollBar().valueChanged.connect(lambda value: append_batch() if pending and value>=details.verticalScrollBar().maximum()-200 else None)
        lay.addWidget(details)
        card.mousePressEvent=toggle_details
        return card

    def _show_budget_transactions(self,budget):
        year=self.year_pick.value(); month=self.month_pick.currentData()
        txns=sorted(self.engine.transactions_for(budget,year,month),key=lambda t:t.get('tx_date',''),reverse=True)
        dlg=QDialog(self); dlg.setWindowTitle(f"{self._name(budget)} — Budget Transactions"); dlg.resize(800,600); dlg.setStyleSheet(f"QDialog{{background:{C['bg']};}}")
        root=QVBoxLayout(dlg); root.addWidget(QLabel(f"{len(txns)} transaction{'s' if len(txns)!=1 else ''} counted toward this budget"))
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame); inner=QWidget(); lay=QVBoxLayout(inner); lay.setSpacing(6); scroll.setWidget(inner); root.addWidget(scroll,1)
        batch_size=50; pending=list(txns)
        def append_batch():
            nonlocal pending
            batch,pending=pending[:batch_size],pending[batch_size:]
            for tx in batch: lay.addWidget(_tx_card(tx))
            if not pending: lay.addStretch()
        append_batch()
        def on_scroll(value):
            sb=scroll.verticalScrollBar()
            if pending and value>=sb.maximum()-200: append_batch()
        scroll.verticalScrollBar().valueChanged.connect(on_scroll)
        close=QPushButton('Close'); close.clicked.connect(dlg.accept); root.addWidget(close)
        dlg.exec_()

    def _deactivate_budget(self,budget):
        self.repo.deactivate(budget['budget_id']); self.refresh()
        Toast.show_message(self, f"{self._name(budget)} budget deactivated", kind='success')

    def _delete_budget(self,budget):
        if QMessageBox.question(self,'Delete Budget',f"Permanently delete {self._name(budget)} budget?",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
            self.repo.delete(budget['budget_id']); self.refresh()
            Toast.show_message(self, f"{self._name(budget)} budget deleted", kind='success')

    def _show_inactive(self):
        rows=self.repo.list_inactive(self.period_type)
        dlg=QDialog(self); dlg.setWindowTitle('Inactive Budgets'); dlg.setMinimumWidth(460); dlg.setStyleSheet(f"QDialog{{background:{C['bg']};}}")
        lay=QVBoxLayout(dlg)
        if not rows: lay.addWidget(QLabel('No inactive budgets for this period.'))
        for b in rows:
            row=QHBoxLayout(); name=QLabel(f"{self._name(b)} · {fmt_money(b['limit_amount'])}"); row.addWidget(name,1)
            react=QPushButton('Reactivate'); react.clicked.connect(lambda _,x=b: self._reactivate_budget(x,dlg)); row.addWidget(react)
            delete=QPushButton('Delete'); delete.clicked.connect(lambda _,x=b: self._delete_budget(x)); row.addWidget(delete); lay.addLayout(row)
        close=QPushButton('Close'); close.clicked.connect(dlg.accept); lay.addWidget(close)
        dlg.exec_()

    def _reactivate_budget(self,budget, dialog=None):
        self.repo.reactivate(budget['budget_id'])
        if dialog: dialog.accept()
        self.refresh()
        Toast.show_message(self, f"{self._name(budget)} budget reactivated", kind='success')

    def _open_editor(self,budget=None):
        period_label='Yearly' if self.period_type=='YEARLY' else 'Monthly'
        dlg=QDialog(self); dlg.setWindowTitle(f"Edit {period_label} Budget" if budget else f"Add {period_label} Budget"); dlg.setMinimumWidth(420); dlg.setStyleSheet(f"QDialog{{background:{C['bg']};}}")
        form=QFormLayout(dlg); form.setContentsMargins(22,18,22,18); form.setSpacing(10)
        scope=QComboBox(); scope.addItem('Category','CATEGORY'); scope.addItem('Money Purpose','PF_CATEGORY'); scope.addItem('Total Personal Spending','TOTAL_EXPENSE'); scope.addItem('Want Spending','NEED_WANT'); scope.addItem('Transaction Group','TRANSACTION_GROUP')
        schedule=QComboBox(); schedule.addItem('Recurring (all future periods)','RECURRING'); schedule.addItem('Selected period only','SELECTED')
        target=QComboBox(); amount=QDoubleSpinBox(); amount.setRange(.01,99999999); amount.setPrefix('₹ '); amount.setDecimals(2); alert=QDoubleSpinBox(); alert.setRange(1,100); alert.setValue(80); alert.setSuffix(' %')
        special_start=QDateEdit(self.special_start.date()); special_start.setCalendarPopup(True)
        special_end=QDateEdit(self.special_end.date()); special_end.setCalendarPopup(True)
        def fill_targets():
            target.clear(); st=scope.currentData(); target.setEnabled(True)
            if st=='CATEGORY':
                for c in self.lookups.list_categories(): target.addItem(c['display_name'],c['category_id'])
            elif st=='PF_CATEGORY':
                for p in self.lookups.list_pf_categories(): target.addItem(p['display_name'],p['pf_id'])
            elif st=='TRANSACTION_GROUP':
                for label,value in [('Regular Spending','REGULAR'),('Transfers','TRANSFER'),('Loans Given','LOAN_GIVEN'),('Loan Repayments','LOAN_REPAYMENT'),('Loans Taken','LOAN_TAKEN'),('EMI Payments','EMI_PAYMENT'),('Fixed Deposits','FD_DEPOSIT'),('Mutual Fund Purchases','MF_PURCHASE'),('Mutual Fund Redemptions','MF_REDEMPTION'),('Split Expenses','SPLIT'),('Split Settlements','SPLIT_SETTLEMENT')]: target.addItem(label,value)
            elif st=='NEED_WANT':
                target.addItem('Need Spending','NEED'); target.addItem('Want Spending','WANT')
            else: target.addItem('All regular personal expenses','ALL')
        scope.currentIndexChanged.connect(fill_targets); fill_targets()
        if budget:
            idx=scope.findData(budget['scope_type']); scope.setCurrentIndex(max(0,idx)); fill_targets(); ti=target.findData(budget['scope_value']); target.setCurrentIndex(max(0,ti)); amount.setValue(budget['limit_amount']); alert.setValue(budget['alert_threshold_pct'])
            si=schedule.findData(budget.get('schedule_type') or 'RECURRING'); schedule.setCurrentIndex(max(0,si))
            if budget.get('start_date'): special_start.setDate(QDate.fromString(budget['start_date'],'yyyy-MM-dd'))
            if budget.get('end_date'): special_end.setDate(QDate.fromString(budget['end_date'],'yyyy-MM-dd'))
        if self.period_type=='SPECIAL':
            schedule.setCurrentIndex(1); schedule.setEnabled(False)
            form.addRow('Schedule',QLabel('One time only — never recurring'))
            form.addRow('Start Date',special_start); form.addRow('End Date',special_end)
        else:
            form.addRow('Apply to',schedule)
        form.addRow('Budget type',scope); form.addRow('Target',target); form.addRow('Yearly limit' if self.period_type=='YEARLY' else 'Monthly limit',amount); form.addRow('Alert at',alert)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Save); buttons.rejected.connect(dlg.reject); buttons.accepted.connect(dlg.accept); form.addRow('',buttons)
        if dlg.exec_()!=QDialog.Accepted:return
        year = self.year_pick.value()
        month = self.month_pick.currentData()
        start = special_start.date().toString('yyyy-MM-dd')
        end = special_end.date().toString('yyyy-MM-dd')
        if self.period_type=='SPECIAL' and special_end.date() < special_start.date():
            QMessageBox.warning(self,'Invalid Special Period','End Date must be on or after Start Date.')
            return
        schedule_type='SPECIAL' if self.period_type=='SPECIAL' else schedule.currentData()
        kwargs={'period_type':self.period_type,'schedule_type':schedule_type,'period_year':year if schedule_type=='SELECTED' else None,'period_month':month if (schedule_type=='SELECTED' and self.period_type=='MONTHLY') else None,'start_date':start if self.period_type=='SPECIAL' else None,'end_date':end if self.period_type=='SPECIAL' else None}
        if self.repo.exists(scope.currentData(),target.currentData(),self.period_type,schedule_type,kwargs['period_year'],kwargs['period_month'],kwargs['start_date'],kwargs['end_date'],budget['budget_id'] if budget else None):
            QMessageBox.warning(self,'Duplicate Budget','An active budget with this same target and schedule already exists.')
            return
        if budget and (budget.get('schedule_type') or 'RECURRING')=='RECURRING' and schedule_type=='SELECTED':
            # "Selected period only" creates an override and preserves the
            # recurring budget for all later periods.
            self.repo.create(scope.currentData(),target.currentData(),amount.value(),alert.value(),**kwargs)
        elif budget:
            self.repo.update(budget['budget_id'],scope.currentData(),target.currentData(),amount.value(),alert.value(),**kwargs)
        else:
            self.repo.create(scope.currentData(),target.currentData(),amount.value(),alert.value(),**kwargs)
        self.refresh()
        Toast.show_message(self, f"{self._name(budget) if budget else target.currentText()} budget {'updated' if budget else 'created'}", kind='success')
