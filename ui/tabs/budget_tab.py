"""Monthly recurring budgets — set once, evaluated every calendar month."""
from datetime import date
from PyQt5.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
                             QFrame,QScrollArea,QDialog,QFormLayout,QComboBox,
                             QDoubleSpinBox,QDialogButtonBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from ui.theme import C
from ui.sidebar import fmt_money
from services.budget_service import BudgetService
from ui.widgets.empty_state import EmptyState


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
        self.month_btn=QPushButton("Monthly"); self.year_btn=QPushButton("Yearly")
        self.month_btn.clicked.connect(lambda:self._set_period("MONTHLY")); self.year_btn.clicked.connect(lambda:self._set_period("YEARLY"))
        periods.addWidget(self.month_btn); periods.addWidget(self.year_btn); periods.addStretch(); root.addLayout(periods)
        self.summary=QLabel(); self.summary.setStyleSheet(f"color:{C['text3']};font-size:12px;font-weight:600;"); root.addWidget(self.summary)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame); scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner=QWidget(); inner.setStyleSheet("background:transparent;"); self.lay=QVBoxLayout(inner); self.lay.setSpacing(10); self.lay.setAlignment(Qt.AlignTop); scroll.setWidget(inner); root.addWidget(scroll,1)

    def on_activated(self): self.refresh()
    def _set_period(self, period):
        self.period_type=period; self.refresh()
    def refresh(self):
        active=f"background:{C['accent']};color:{C['on_accent']};border:none;"
        inactive=f"background:{C['surface']};color:{C['text2']};border:1px solid {C['border']};"
        for btn,period in ((self.month_btn,'MONTHLY'),(self.year_btn,'YEARLY')):
            btn.setStyleSheet(f"QPushButton{{{active if self.period_type==period else inactive}border-radius:8px;padding:7px 16px;font-weight:700;}}")
        is_year=self.period_type=='YEARLY'
        self.title.setText('📊  Yearly Budgets' if is_year else '📊  Monthly Budgets')
        self.sub.setText('Set a limit once — it automatically applies every calendar year.' if is_year else 'Set a limit once — it automatically applies every calendar month.')
        self.add.setText('＋ Add Yearly Budget' if is_year else '＋ Add Monthly Budget')
        while self.lay.count():
            it=self.lay.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        today=date.today(); budgets=self.engine.check_budgets(today.year,today.month,self.period_type)
        total_limit=sum(b['limit_amount'] for b in budgets); total_spent=sum(b['spent'] for b in budgets)
        period_label=str(today.year) if self.period_type=='YEARLY' else today.strftime('%B %Y')
        self.summary.setText(f"{period_label} · {len(budgets)} active budget{'s' if len(budgets)!=1 else ''} · {fmt_money(total_spent)} used of {fmt_money(total_limit)}")
        if not budgets:
            word='yearly' if self.period_type=='YEARLY' else 'monthly'
            self.lay.addWidget(EmptyState("📊",f"No {word} budgets yet",f"Create a category, total-expense, or Want-spending limit. It will recur automatically every {'year' if self.period_type=='YEARLY' else 'month'}.",f"＋ Add {word.title()} Budget",self._open_editor)); self.lay.addStretch(); return
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
        card=QFrame(); card.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-left:4px solid {color};border-radius:10px;}}QLabel{{background:transparent;border:none;}}")
        lay=QVBoxLayout(card); lay.setContentsMargins(16,12,16,12); lay.setSpacing(7)
        top=QHBoxLayout(); name=QLabel(self._name(b)); name.setStyleSheet(f"font-size:15px;font-weight:800;color:{C['text']};"); top.addWidget(name); top.addStretch()
        edit=QPushButton("Edit"); edit.setCursor(QCursor(Qt.PointingHandCursor)); edit.clicked.connect(lambda: self._open_editor(b)); top.addWidget(edit)
        off=QPushButton("Deactivate"); off.setCursor(QCursor(Qt.PointingHandCursor)); off.clicked.connect(lambda: (self.repo.deactivate(b['budget_id']),self.refresh())); top.addWidget(off); lay.addLayout(top)
        value=QLabel(f"{fmt_money(b['spent'])} of {fmt_money(b['limit_amount'])}  ·  {pct:.0f}% used"); value.setStyleSheet(f"font-size:14px;font-weight:800;color:{color};"); lay.addWidget(value)
        bar=QFrame(); bar.setFixedHeight(8); bar.setStyleSheet(f"background:{C['border2']};border-radius:4px;"); bl=QHBoxLayout(bar); bl.setContentsMargins(0,0,0,0); bl.setSpacing(0); fill=QFrame(); fill.setStyleSheet(f"background:{color};border-radius:4px;"); bl.addWidget(fill,max(1,min(100,int(pct)))); bl.addStretch(max(1,100-min(100,int(pct)))); lay.addWidget(bar)
        remaining='over budget by '+fmt_money(abs(b['remaining'])) if b['remaining']<0 else fmt_money(b['remaining'])+' remaining'
        cap=QLabel(f"Alert at {b['alert_threshold_pct']:.0f}% · {remaining}"); cap.setStyleSheet(f"font-size:11px;color:{C['text3']};"); lay.addWidget(cap)
        if self.period_type=='YEARLY':
            today=date.today(); expected=(today.timetuple().tm_yday / (366 if today.year%4==0 else 365))*100
            pace='ahead of plan' if pct > expected + 5 else ('behind plan' if pct < expected - 5 else 'on pace')
            pace_lbl=QLabel(f"Year progress {expected:.0f}% · spending {pct:.0f}% · {pace}")
            pace_lbl.setStyleSheet(f"font-size:11px;color:{C['text3']};font-weight:600;"); lay.addWidget(pace_lbl)
        return card

    def _open_editor(self,budget=None):
        period_label='Yearly' if self.period_type=='YEARLY' else 'Monthly'
        dlg=QDialog(self); dlg.setWindowTitle(f"Edit {period_label} Budget" if budget else f"Add {period_label} Budget"); dlg.setMinimumWidth(420); dlg.setStyleSheet(f"QDialog{{background:{C['bg']};}}")
        form=QFormLayout(dlg); form.setContentsMargins(22,18,22,18); form.setSpacing(10)
        scope=QComboBox(); scope.addItem('Category','CATEGORY'); scope.addItem('Total Personal Spending','TOTAL_EXPENSE'); scope.addItem('Want Spending','NEED_WANT')
        target=QComboBox(); amount=QDoubleSpinBox(); amount.setRange(.01,99999999); amount.setPrefix('₹ '); amount.setDecimals(2); alert=QDoubleSpinBox(); alert.setRange(1,100); alert.setValue(80); alert.setSuffix(' %')
        def fill_targets():
            target.clear(); st=scope.currentData(); target.setEnabled(st=='CATEGORY')
            if st=='CATEGORY':
                for c in self.lookups.list_categories(): target.addItem(c['display_name'],c['category_id'])
            else: target.addItem('All regular personal expenses' if st=='TOTAL_EXPENSE' else 'Regular expenses marked Want','ALL' if st=='TOTAL_EXPENSE' else 'WANT')
        scope.currentIndexChanged.connect(fill_targets); fill_targets()
        if budget:
            idx=scope.findData(budget['scope_type']); scope.setCurrentIndex(max(0,idx)); fill_targets(); ti=target.findData(budget['scope_value']); target.setCurrentIndex(max(0,ti)); amount.setValue(budget['limit_amount']); alert.setValue(budget['alert_threshold_pct'])
        form.addRow('Repeats',QLabel('Every calendar year' if self.period_type=='YEARLY' else 'Every calendar month'))
        form.addRow('Budget type',scope); form.addRow('Target',target); form.addRow('Yearly limit' if self.period_type=='YEARLY' else 'Monthly limit',amount); form.addRow('Alert at',alert)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Save); buttons.rejected.connect(dlg.reject); buttons.accepted.connect(dlg.accept); form.addRow('',buttons)
        if dlg.exec_()!=QDialog.Accepted:return
        if budget:self.repo.update(budget['budget_id'],scope.currentData(),target.currentData(),amount.value(),alert.value())
        else:self.repo.create(scope.currentData(),target.currentData(),amount.value(),alert.value(),self.period_type)
        self.refresh()
