"""Cards Tab — Professional credit card management with flip carousel."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QFrame, QStackedWidget, QDialog,
                              QFormLayout, QLineEdit, QComboBox, QSpinBox,
                              QDoubleSpinBox, QMessageBox, QSizePolicy,
                              QGraphicsView, QGraphicsScene, QGraphicsObject,
                              QScrollArea, QInputDialog, QGridLayout, QSplitter)
from PyQt5.QtCore import (Qt, QRectF, QPointF, QTimer, QPropertyAnimation,
                           QEasingCurve, pyqtProperty, pyqtSignal, QSize)
from PyQt5.QtGui import (QPainter, QColor, QLinearGradient, QFont,
                          QPainterPath, QPen, QTransform)
from datetime import date, datetime, timedelta
from collections import OrderedDict
from ui.theme import C
from ui.sidebar import fmt_money
from ui.tabs.database_tab import _tx_card, _day_header, _month_header
import uuid

CARD_W = 320; CARD_H = 200; CARD_RADIUS = 16; GAP = 40
STRIPE_RECT = QRectF(-CARD_W / 2, -CARD_H / 2 + 20, CARD_W, 32)
EASE_FACTOR = 0.16; PX_PER_UNIT = CARD_W * 0.9; DRAG_THRESHOLD = 6

DEFAULT_GRADIENTS = [
    ("#3a3a3a", "#0f0f0f"), ("#1c3d5a", "#0a0f14"), ("#4b2e2e", "#120909"),
    ("#2e4b34", "#0a120c"), ("#3a2e4b", "#0f0a14"), ("#4b3a1a", "#120d05"),
    ("#1a3a3a", "#050f0f"), ("#4b1a3a", "#12050d"), ("#2a2a4b", "#08081b"),
    ("#4b3a2a", "#150f08"),
]

PAYMENT_METHODS = [
    "PHONEPAY", "SLICE", "DIRECT TRANSFER", "CASH", "AMAZON PAY",
    "FLIPKART 3I", "ATM", "CRED APP", "SUPER MONEY", "PAYTM",
    "GOOGLE PAY", "NAVY UPI", "BHIM UPI", "AIRTEL PAY", "NETBANKING",
    "CHEQUE", "FED UPI", "AXIS UPI", "NAMMA METRO CARD", "YONO",
    "CANARA AI", "SIB MIRROR", "OTHER",
]

def smoothstep(t):
    t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)

def _tab_btn_active():
    return f"QPushButton{{background:{C['accent']};color:white;border:1px solid {C['accent']};border-radius:8px;padding:8px 16px;font-size:13px;font-weight:700;}}"

def _tab_btn_inactive():
    return f"QPushButton{{background:{C['surface']};color:{C['text2']};border:1px solid {C['border']};border-radius:8px;padding:8px 16px;font-size:13px;font-weight:600;}}QPushButton:hover{{border-color:{C['accent']};color:{C['accent']};}}"


# ═══════════════════════════════════════════════
# CARD ITEM
# ═══════════════════════════════════════════════

class CardItem(QGraphicsObject):
    stripe_clicked = pyqtSignal(str)
    def __init__(self, card_data, index, utilization=0.0):
        super().__init__()
        self.data = card_data; self.index = index; self.show_back = False
        self._flip_scale = 1.0; self._anim = None; self._stripe_hover = False
        self._utilization = utilization; self.setAcceptHoverEvents(True)
    def getFlipScale(self): return self._flip_scale
    def setFlipScale(self, v): self._flip_scale = v; self.update()
    flipScale = pyqtProperty(float, getFlipScale, setFlipScale)
    def boundingRect(self): return QRectF(-CARD_W/2-2, -CARD_H/2-2, CARD_W+4, CARD_H+4)
    def flip(self):
        if self._anim and self._anim.state() == QPropertyAnimation.Running: return
        a = QPropertyAnimation(self, b"flipScale"); a.setDuration(130)
        a.setStartValue(1.0); a.setEndValue(0.0); a.setEasingCurve(QEasingCurve.InQuad)
        a.finished.connect(self._on_half_flip); self._anim = a; a.start()
    def _on_half_flip(self):
        self.show_back = not self.show_back
        a = QPropertyAnimation(self, b"flipScale"); a.setDuration(130)
        a.setStartValue(0.0); a.setEndValue(1.0); a.setEasingCurve(QEasingCurve.OutQuad)
        self._anim = a; a.start()
    def hoverMoveEvent(self, e):
        h = self.show_back and STRIPE_RECT.contains(e.pos())
        if h != self._stripe_hover: self._stripe_hover = h; self.setCursor(Qt.PointingHandCursor if h else Qt.ArrowCursor); self.update()
        super().hoverMoveEvent(e)
    def hoverLeaveEvent(self, e):
        if self._stripe_hover: self._stripe_hover = False; self.setCursor(Qt.ArrowCursor); self.update()
        super().hoverLeaveEvent(e)
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = CARD_W, CARD_H; rect = QRectF(-w/2, -h/2, w, h)
        painter.save(); painter.setPen(Qt.NoPen); painter.setBrush(QColor(0,0,0,110))
        painter.drawRoundedRect(QRectF(-w/2, -h/2+8, w, h), CARD_RADIUS, CARD_RADIUS); painter.restore()
        g = QLinearGradient(-w/2, -h/2, w/2, h/2)
        g.setColorAt(0, QColor(self.data.get("card_color_1","#3a3a3a")))
        g.setColorAt(1, QColor(self.data.get("card_color_2","#0f0f0f")))
        painter.setPen(Qt.NoPen); painter.setBrush(g); painter.drawRoundedRect(rect, CARD_RADIUS, CARD_RADIUS)
        if not self.show_back: self._draw_front(painter)
        else: self._draw_back(painter)
        p = QPen(QColor(255,255,255,40)); p.setWidth(1); painter.setPen(p); painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5,0.5,-0.5,-0.5), CARD_RADIUS, CARD_RADIUS)
    def _draw_front(self, painter):
        w, h = CARD_W, CARD_H
        painter.setPen(QColor(255,255,255,235)); f=QFont("Arial",13,QFont.Bold); f.setLetterSpacing(QFont.AbsoluteSpacing,0.6); painter.setFont(f)
        painter.drawText(QRectF(-w/2+20,-h/2+14,w-40,20), Qt.AlignLeft|Qt.AlignVCenter, self.data.get("issuer_bank","BANK"))
        brand = self.data.get("card_brand","")
        if brand: painter.setPen(QColor(255,255,255,170)); painter.setFont(QFont("Arial",10)); painter.drawText(QRectF(-w/2+20,-h/2+34,w-40,16), Qt.AlignLeft|Qt.AlignVCenter, brand)
        cr = QRectF(-w/2+24,-13,34,26); cg=QLinearGradient(cr.topLeft(),cr.bottomLeft()); cg.setColorAt(0,QColor("#f2f2f2")); cg.setColorAt(1,QColor("#999999"))
        painter.setPen(Qt.NoPen); painter.setBrush(cg); painter.drawRoundedRect(cr,4,4)
        painter.setPen(QPen(QColor("#777777"),1))
        for i in range(1,3): x=cr.left()+cr.width()*i/3; painter.drawLine(QPointF(x,cr.top()),QPointF(x,cr.bottom()))
        painter.drawLine(QPointF(cr.left(),cr.center().y()),QPointF(cr.right(),cr.center().y()))
        bx=-w/2+20; by=22; bw=w-40; bh=14
        painter.setPen(Qt.NoPen); painter.setBrush(QColor(255,255,255,25)); painter.drawRoundedRect(QRectF(bx,by,bw,bh),4,4)
        util=max(0.0,min(1.0,self._utilization)); fw=bw*util
        bc = QColor("#10B981") if util<0.3 else (QColor("#F59E0B") if util<0.7 else QColor("#EF4444"))
        if fw>0: painter.setBrush(bc); painter.drawRoundedRect(QRectF(bx,by,fw,bh),4,4)
        painter.setPen(QColor(255,255,255,200)); painter.setFont(QFont("Arial",7,QFont.Bold))
        painter.drawText(QRectF(bx,by,bw,bh), Qt.AlignCenter, f"{util*100:.0f}% utilized")
        painter.setPen(QColor(255,255,255,235)); tf=QFont("Arial",14,QFont.Bold); tf.setItalic(True); tf.setLetterSpacing(QFont.AbsoluteSpacing,1.0); painter.setFont(tf)
        painter.drawText(QRectF(-w/2,h/2-52,w-20,22), Qt.AlignRight|Qt.AlignVCenter, self.data.get("card_network","VISA"))
        cls=self.data.get("card_class","")
        if cls: painter.setPen(QColor(255,255,255,150)); painter.setFont(QFont("Arial",10)); painter.drawText(QRectF(-w/2,h/2-32,w-20,18), Qt.AlignRight|Qt.AlignVCenter, cls)
    def _draw_back(self, painter):
        w, h = CARD_W, CARD_H
        sc = QColor(35,35,35,235) if self._stripe_hover else QColor(0,0,0,220)
        painter.setPen(Qt.NoPen); painter.setBrush(sc); painter.drawRect(STRIPE_RECT)
        painter.setPen(QColor(255,255,255,220 if self._stripe_hover else 150))
        painter.setFont(QFont("Arial",9,QFont.DemiBold))
        painter.drawText(STRIPE_RECT, Qt.AlignCenter, "VIEW CARD DETAILS  \u2192" if self._stripe_hover else "VIEW CARD DETAILS")
        painter.setPen(QColor(255,255,255,200)); painter.setFont(QFont("Arial",11))
        painter.drawText(QRectF(-w/2+20,h/2-80,w-40,20), Qt.AlignLeft|Qt.AlignVCenter, self.data.get("cardholder_name","CARDHOLDER"))
        mono=QFont("Courier New",11,QFont.DemiBold); painter.setFont(mono); painter.setPen(QColor(255,255,255,235))
        number = self.data.get("card_number","") or f"XXXX  XXXX  XXXX  {self.data.get('last_four','0000')}"
        fm=painter.fontMetrics(); mw=w-40
        if fm.horizontalAdvance(number)>mw:
            while fm.horizontalAdvance(number)>mw and len(number)>4: number=number[:-1]
        painter.drawText(QRectF(-w/2+20,h/2-56,w-40,20), Qt.AlignLeft|Qt.AlignVCenter, number)
        painter.setFont(QFont("Courier New",9)); painter.setPen(QColor(255,255,255,170))
        em=self.data.get("expiry_month",12); ey=self.data.get("expiry_year",2028)
        painter.drawText(QRectF(-w/2+20,h/2-34,w-40,20), Qt.AlignLeft|Qt.AlignVCenter, f"Valid: {em:02d}/{str(ey)[-2:]}")


# ═══════════════════════════════════════════════
# CAROUSEL VIEW
# ═══════════════════════════════════════════════

class CarouselView(QGraphicsView):
    card_clicked = pyqtSignal(str)
    def __init__(self, cards_data=None, utilizations=None, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setStyleSheet("background-color:#111827;border:none;border-radius:12px;")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.StrongFocus); self.setMouseTracking(True)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, True)
        self.scene=QGraphicsScene(self); self.scene.setItemIndexMethod(QGraphicsScene.NoIndex); self.setScene(self.scene)
        self.card_count=0; self.items=[]; self.progress=0.0; self.target_progress=0.0
        self._dragging=False; self._press_pos=None; self._press_item=None; self._drag_start_progress=0.0
        self.timer=QTimer(self); self.timer.timeout.connect(self._on_tick); self.timer.start(16)
        if cards_data: self.load_cards(cards_data, utilizations)
    def load_cards(self, cards_data, utilizations=None):
        for i in self.items: self.scene.removeItem(i)
        self.items.clear(); self.card_count=len(cards_data); self.progress=0.0; self.target_progress=0.0
        for i, data in enumerate(cards_data):
            u=(utilizations or{}).get(data.get("account_id",""),0.0)
            item=CardItem(data,i,u); item.stripe_clicked.connect(self.card_clicked.emit)
            self.scene.addItem(item); self.items.append(item)
    def _on_tick(self):
        self.progress+=(self.target_progress-self.progress)*EASE_FACTOR
        cx=self.viewport().width()/2; cy=self.viewport().height()/2
        for item in self.items:
            off=item.index-self.progress; half=self.card_count/2
            while off>half: off-=self.card_count
            while off<-half: off+=self.card_count
            ao=abs(off); sign=1 if off>0 else(-1 if off<0 else 0)
            if ao>3.2: item.setVisible(False); continue
            item.setVisible(True)
            if ao<=1: t=smoothstep(ao); x=sign*t*(CARD_W*0.62+GAP); sc=1-t*0.30; op=1.0; z=100-t*40
            elif ao<=2: t=smoothstep(ao-1); x=sign*((CARD_W*0.62+GAP)+t*(CARD_W*0.5)); sc=0.70-t*0.20; op=1.0-t*0.4; z=60-t*40
            else: t=smoothstep(min(ao-2,1)); x=sign*((CARD_W*0.62+GAP+CARD_W*0.5)+t*(CARD_W*0.6)); sc=max(0.2,0.50-t*0.3); op=max(0.0,0.6-t*0.6); z=20-t*20
            tr=QTransform(); tr.translate(cx+x,cy); tr.scale(sc*item.flipScale,sc)
            item.setTransform(tr); item.setZValue(z); item.setOpacity(op); item.update()
        self.viewport().update()
    def mousePressEvent(self, e):
        self._press_pos=e.pos(); self._press_item=self.itemAt(e.pos()); self._dragging=False; self._drag_start_progress=self.target_progress; super().mousePressEvent(e)
    def mouseMoveEvent(self, e):
        if e.buttons()&Qt.LeftButton and self._press_pos:
            dx=e.pos().x()-self._press_pos.x()
            if abs(dx)>DRAG_THRESHOLD: self._dragging=True
            if self._dragging: self.target_progress=self._drag_start_progress-dx/PX_PER_UNIT
        super().mouseMoveEvent(e)
    def mouseReleaseEvent(self, e):
        if self._dragging: self.target_progress=round(self.target_progress)
        else:
            item=self._press_item
            if isinstance(item,CardItem):
                lp=item.mapFromScene(self.mapToScene(e.pos()))
                if item.show_back and STRIPE_RECT.contains(lp): self.card_clicked.emit(item.data.get("card_id",""))
                else: item.flip()
        self._dragging=False; self._press_pos=None; self._press_item=None; super().mouseReleaseEvent(e)
    def wheelEvent(self, e): self.target_progress-=e.angleDelta().y()/240.0; e.accept()
    def keyPressEvent(self, e):
        if e.key()==Qt.Key_Left: self.target_progress=round(self.target_progress)-1
        elif e.key()==Qt.Key_Right: self.target_progress=round(self.target_progress)+1
        elif e.key()==Qt.Key_Space:
            nearest=min(self.items,key=lambda it:abs(((it.index-self.progress+self.card_count/2)%self.card_count)-self.card_count/2)); nearest.flip()
        else: super().keyPressEvent(e)
    def resizeEvent(self, e): self.scene.setSceneRect(0,0,self.viewport().width(),self.viewport().height()); super().resizeEvent(e)


# ═══════════════════════════════════════════════
# PREVIEW WIDGETS (Add Card dialog)
# ═══════════════════════════════════════════════

class CardPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setFixedSize(CARD_W, CARD_H)
        self._data = {"issuer_bank":"BANK","card_brand":"","card_network":"VISA","card_class":"","last_four":"0000","card_color_1":"#3a3a3a","card_color_2":"#0f0f0f"}
    def update_data(self, **kw): self._data.update(kw); self.update()
    def paintEvent(self, event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing); w,h=CARD_W,CARD_H; rect=QRectF(0,0,w,h)
        g=QLinearGradient(0,0,w,h); g.setColorAt(0,QColor(self._data.get("card_color_1","#3a3a3a"))); g.setColorAt(1,QColor(self._data.get("card_color_2","#0f0f0f")))
        p.setPen(Qt.NoPen); p.setBrush(g); p.drawRoundedRect(rect,CARD_RADIUS,CARD_RADIUS)
        p.setPen(QColor(255,255,255,235)); bf=QFont("Arial",13,QFont.Bold); bf.setLetterSpacing(QFont.AbsoluteSpacing,0.6); p.setFont(bf)
        p.drawText(QRectF(20,14,w-40,20),Qt.AlignLeft|Qt.AlignVCenter,self._data.get("issuer_bank","BANK"))
        brand=self._data.get("card_brand","")
        if brand: p.setPen(QColor(255,255,255,170)); p.setFont(QFont("Arial",10)); p.drawText(QRectF(20,34,w-40,16),Qt.AlignLeft|Qt.AlignVCenter,brand)
        chip=QRectF(24,h/2-13,34,26); cg=QLinearGradient(chip.topLeft(),chip.bottomLeft()); cg.setColorAt(0,QColor("#f2f2f2")); cg.setColorAt(1,QColor("#999999"))
        p.setPen(Qt.NoPen); p.setBrush(cg); p.drawRoundedRect(chip,4,4)
        network=self._data.get("card_network","VISA"); p.setPen(QColor(255,255,255,235)); tf=QFont("Arial",14,QFont.Bold); tf.setItalic(True); p.setFont(tf)
        p.drawText(QRectF(0,h-52,w-20,22),Qt.AlignRight|Qt.AlignVCenter,network)
        cls=self._data.get("card_class","")
        if cls: p.setPen(QColor(255,255,255,150)); p.setFont(QFont("Arial",10)); p.drawText(QRectF(0,h-32,w-20,18),Qt.AlignRight|Qt.AlignVCenter,cls)
        pen=QPen(QColor(255,255,255,40)); pen.setWidth(1); p.setPen(pen); p.setBrush(Qt.NoBrush); p.drawRoundedRect(rect.adjusted(0.5,0.5,-0.5,-0.5),CARD_RADIUS,CARD_RADIUS); p.end()

class CardBackPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setFixedSize(CARD_W, CARD_H)
        self._data = {"cardholder_name":"CARDHOLDER","last_four":"0000","expiry_month":12,"expiry_year":2028,"card_color_1":"#3a3a3a","card_color_2":"#0f0f0f"}
    def update_data(self, **kw): self._data.update(kw); self.update()
    def paintEvent(self, event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing); w,h=CARD_W,CARD_H; rect=QRectF(0,0,w,h)
        g=QLinearGradient(0,0,w,h); g.setColorAt(0,QColor(self._data.get("card_color_1","#3a3a3a"))); g.setColorAt(1,QColor(self._data.get("card_color_2","#0f0f0f")))
        p.setPen(Qt.NoPen); p.setBrush(g); p.drawRoundedRect(rect,CARD_RADIUS,CARD_RADIUS)
        p.setBrush(QColor(0,0,0,220)); p.drawRect(QRectF(0,20,w,32))
        p.setPen(QColor(255,255,255,150)); p.setFont(QFont("Arial",9,QFont.DemiBold)); p.drawText(QRectF(0,20,w,32),Qt.AlignCenter,"VIEW CARD DETAILS")
        p.setPen(QColor(255,255,255,200)); p.setFont(QFont("Arial",11)); p.drawText(QRectF(20,h-80,w-40,20),Qt.AlignLeft|Qt.AlignVCenter,self._data.get("cardholder_name","CARDHOLDER"))
        last4=self._data.get("last_four","0000")
        p.setPen(QColor(255,255,255,235)); p.setFont(QFont("Courier New",11,QFont.DemiBold)); p.drawText(QRectF(20,h-56,w-40,20),Qt.AlignLeft|Qt.AlignVCenter,f"XXXX  XXXX  XXXX  {last4}")
        em=self._data.get("expiry_month",12); ey=self._data.get("expiry_year",2028)
        p.setPen(QColor(255,255,255,170)); p.setFont(QFont("Courier New",9)); p.drawText(QRectF(20,h-34,w-40,20),Qt.AlignLeft|Qt.AlignVCenter,f"Valid: {em:02d}/{str(ey)[-2:]}")
        pen=QPen(QColor(255,255,255,40)); pen.setWidth(1); p.setPen(pen); p.setBrush(Qt.NoBrush); p.drawRoundedRect(rect.adjusted(0.5,0.5,-0.5,-0.5),CARD_RADIUS,CARD_RADIUS); p.end()


# ═══════════════════════════════════════════════
# ADD CARD DIALOG
# ═══════════════════════════════════════════════

class AddCardDialog(QDialog):
    card_added = pyqtSignal()
    def __init__(self, cards_repo, accounts_repo, parent=None):
        super().__init__(parent); self.cr=cards_repo; self.acct=accounts_repo
        self.setWindowTitle("Add Credit Card"); self.setMinimumWidth(600)
        self.setStyleSheet(f"QDialog{{background:{C['bg']};}}"); self._build()
    def _build(self):
        lay=QHBoxLayout(self); lay.setContentsMargins(24,24,24,24); lay.setSpacing(20)
        fc=QVBoxLayout(); fc.setSpacing(8)
        hdr=QLabel("💳  Add New Credit Card"); hdr.setStyleSheet("font-size:18px;font-weight:800;color:#111827;"); fc.addWidget(hdr)
        form=QFormLayout(); form.setSpacing(8); form.setLabelAlignment(Qt.AlignRight)
        self.card_name=QLineEdit(); self.card_name.setPlaceholderText("e.g. AMAZON PAY ICICI CARD"); self.card_name.textChanged.connect(self._upd); form.addRow("Card Name *",self.card_name)
        self.issuer=QLineEdit(); self.issuer.setPlaceholderText("e.g. ICICI BANK"); self.issuer.textChanged.connect(self._upd); form.addRow("Bank *",self.issuer)
        self.brand=QLineEdit(); self.brand.setPlaceholderText("e.g. AMAZON PAY"); self.brand.textChanged.connect(self._upd); form.addRow("Co-Brand",self.brand)
        self.network=QComboBox(); self.network.addItems(["VISA","MASTERCARD","RUPAY","AMEX","DINERS","BAJAJ","OTHER"]); self.network.currentTextChanged.connect(self._upd); form.addRow("Network",self.network)
        self.card_class=QLineEdit(); self.card_class.setPlaceholderText("e.g. Platinum, Signature"); self.card_class.textChanged.connect(self._upd); form.addRow("Class",self.card_class)
        self.last_four=QLineEdit(); self.last_four.setMaxLength(4); self.last_four.setPlaceholderText("Last 4 digits"); self.last_four.textChanged.connect(self._upd); form.addRow("Last 4 Digits",self.last_four)
        self.cardholder=QLineEdit(); self.cardholder.setPlaceholderText("Name as on card"); self.cardholder.textChanged.connect(self._upd); form.addRow("Cardholder Name",self.cardholder)
        self.credit_limit=QDoubleSpinBox(); self.credit_limit.setRange(0,99999999); self.credit_limit.setPrefix("₹ "); self.credit_limit.setDecimals(0); form.addRow("Credit Limit *",self.credit_limit)
        er=QHBoxLayout(); self.expiry_month=QSpinBox(); self.expiry_month.setRange(1,12); self.expiry_month.setValue(12); self.expiry_year=QSpinBox(); self.expiry_year.setRange(2024,2040); self.expiry_year.setValue(2028)
        self.expiry_month.valueChanged.connect(self._upd); self.expiry_year.valueChanged.connect(self._upd)
        er.addWidget(self.expiry_month); er.addWidget(QLabel("/")); er.addWidget(self.expiry_year); er.addStretch(); form.addRow("Expiry",er)
        self.statement_date=QLineEdit(); self.statement_date.setPlaceholderText("e.g. 20th"); form.addRow("Statement Date",self.statement_date)
        self.billing_day=QSpinBox(); self.billing_day.setRange(1,28); self.billing_day.setValue(1); form.addRow("Billing Day",self.billing_day)
        self.grace_days=QSpinBox(); self.grace_days.setRange(0,55); self.grace_days.setValue(20); form.addRow("Grace Period (days)",self.grace_days)
        self.annual_fee=QDoubleSpinBox(); self.annual_fee.setRange(0,99999); self.annual_fee.setPrefix("₹ "); self.annual_fee.setDecimals(0); form.addRow("Annual Fee",self.annual_fee)
        self.color_idx=QComboBox()
        for i in range(len(DEFAULT_GRADIENTS)): self.color_idx.addItem(f"Style {i+1}")
        self.color_idx.currentIndexChanged.connect(self._upd); form.addRow("Card Style",self.color_idx)
        fc.addLayout(form)
        br=QHBoxLayout(); br.addStretch(); c=QPushButton("Cancel"); c.clicked.connect(self.reject); br.addWidget(c)
        a=QPushButton("  Add Card  "); a.setObjectName("primary"); a.clicked.connect(self._save); br.addWidget(a); fc.addLayout(br); lay.addLayout(fc)
        pc=QVBoxLayout(); pc.setSpacing(8)
        fl=QLabel("Front"); fl.setStyleSheet(f"color:{C['text2']};font-size:13px;font-weight:700;"); pc.addWidget(fl)
        self.preview=CardPreviewWidget(); pc.addWidget(self.preview)
        bl=QLabel("Back"); bl.setStyleSheet(f"color:{C['text2']};font-size:13px;font-weight:700;"); pc.addWidget(bl)
        self.back_preview=CardBackPreviewWidget(); pc.addWidget(self.back_preview); pc.addStretch(); lay.addLayout(pc)
    def _upd(self):
        c1,c2=DEFAULT_GRADIENTS[self.color_idx.currentIndex()]
        d=dict(issuer_bank=self.issuer.text().strip() or "BANK",card_brand=self.brand.text().strip(),card_network=self.network.currentText(),card_class=self.card_class.text().strip(),cardholder_name=self.cardholder.text().strip() or "CARDHOLDER",last_four=self.last_four.text().strip() or "0000",expiry_month=self.expiry_month.value(),expiry_year=self.expiry_year.value(),card_color_1=c1,card_color_2=c2)
        self.preview.update_data(**d); self.back_preview.update_data(**d)
    def _save(self):
        name=self.card_name.text().strip(); bank=self.issuer.text().strip(); limit=self.credit_limit.value()
        if not name or not bank or limit<=0: QMessageBox.warning(self,"Missing","Card name, bank, and credit limit required."); return
        existing=None
        for a in self.acct.list_active():
            if a["display_name"].upper()==name.upper(): existing=a; break
        if existing: aid=existing["account_id"]
        else:
            aid=str(uuid.uuid4())
            self.acct.create(account_id=aid,display_name=name,short_label=name[:8].upper(),account_type="CREDIT_CARD",credit_limit=limit,opening_balance=0,color_hex="#7C3AED")
        c1,c2=DEFAULT_GRADIENTS[self.color_idx.currentIndex()]
        self.cr.create(account_id=aid,card_name=name,issuer_bank=bank,card_brand=self.brand.text().strip(),card_network=self.network.currentText(),card_class=self.card_class.text().strip(),last_four=self.last_four.text().strip() or "0000",cardholder_name=self.cardholder.text().strip() or name.upper(),expiry_month=self.expiry_month.value(),expiry_year=self.expiry_year.value(),statement_date=self.statement_date.text().strip(),billing_day=self.billing_day.value(),grace_days=self.grace_days.value(),annual_fee=self.annual_fee.value(),card_color_1=c1,card_color_2=c2)
        self.card_added.emit(); self.accept()


# ═══════════════════════════════════════════════
# SETTLEMENT POPUP DIALOG (fix 6: custom value)
# ═══════════════════════════════════════════════

class SettlementDialog(QDialog):
    settled = pyqtSignal()
    def __init__(self, card, cards_repo, tx_repo, accounts_repo, bal_svc, parent=None):
        super().__init__(parent)
        self.card=card; self.cr=cards_repo; self.tx_repo=tx_repo; self.acct=accounts_repo; self.bal=bal_svc
        self.setWindowTitle("Settle Card Bill"); self.setMinimumWidth(480)
        self.setStyleSheet(f"QDialog{{background:{C['bg']};}}"); self._build()
    def _build(self):
        lay=QVBoxLayout(self); lay.setContentsMargins(24,24,24,24); lay.setSpacing(14)
        lay.addWidget(QLabel(f"💰  Settle — {self.card.get('card_name','Card')}"))
        limit=self.card.get("credit_limit",0) or self.card.get("acct_limit",0)
        balance=abs(self.bal.get_balance(self.card["account_id"]))
        cycle=self.cr.latest_cycle(self.card["account_id"])
        stmt_due=cycle.get("total_due",0) if cycle else 0
        min_due=cycle.get("minimum_due",0) if cycle else 0
        self.settle_opt=QComboBox()
        self.settle_opt.addItem(f"Current Outstanding — {fmt_money(balance)}",balance)
        self.settle_opt.addItem(f"Statement Outstanding — {fmt_money(stmt_due)}",stmt_due)
        self.settle_opt.addItem(f"Minimum Outstanding — {fmt_money(min_due)}",min_due)
        self.settle_opt.addItem("Custom Amount...", -1)
        self.settle_opt.setMinimumHeight(36); self.settle_opt.currentIndexChanged.connect(self._on_opt_changed)
        lay.addWidget(QLabel("Repay Option:")); lay.addWidget(self.settle_opt)
        # Custom amount (hidden unless "Custom Amount..." selected)
        self.custom_row = QWidget(); custom_lay = QHBoxLayout(self.custom_row); custom_lay.setContentsMargins(0,0,0,0)
        custom_lay.addWidget(QLabel("Amount:"))
        self.custom_amt = QDoubleSpinBox(); self.custom_amt.setRange(0,99999999); self.custom_amt.setPrefix("₹ "); self.custom_amt.setDecimals(0); self.custom_amt.setMinimumHeight(36)
        custom_lay.addWidget(self.custom_amt, 1)
        self.custom_row.hide(); lay.addWidget(self.custom_row)
        lay.addWidget(QLabel("Pay From:"))
        self.settle_src=QComboBox()
        for a in self.acct.list_active():
            if a["account_type"]!="CREDIT_CARD": self.settle_src.addItem(a["display_name"],a["account_id"])
        self.settle_src.setMinimumHeight(36); lay.addWidget(self.settle_src)
        lay.addWidget(QLabel("Payment Method:"))
        self.settle_method=QComboBox(); self.settle_method.addItems(PAYMENT_METHODS); self.settle_method.setMinimumHeight(36); lay.addWidget(self.settle_method)
        br=QHBoxLayout(); br.addStretch()
        c=QPushButton("Cancel"); c.clicked.connect(self.reject); br.addWidget(c)
        rb=QPushButton("  Settle  "); rb.setStyleSheet(f"QPushButton{{background:{C['accent']};color:white;border:none;border-radius:8px;padding:10px 24px;font-size:14px;font-weight:700;}}QPushButton:hover{{background:#4338CA;}}")
        rb.setMinimumHeight(40); rb.setCursor(Qt.PointingHandCursor); rb.clicked.connect(self._repay); br.addWidget(rb)
        lay.addLayout(br)
    def _on_opt_changed(self, idx):
        is_custom = self.settle_opt.currentData() == -1
        self.custom_row.setVisible(is_custom)
    def _repay(self):
        if self.settle_opt.currentData() == -1:
            amt = self.custom_amt.value()
        else:
            amt = self.settle_opt.currentData()
        src_id=self.settle_src.currentData(); method=self.settle_method.currentText()
        if not amt or amt<=0: QMessageBox.warning(self,"Invalid","Enter a valid amount."); return
        if not src_id: QMessageBox.warning(self,"No Source","Select a source account."); return
        today=date.today().isoformat(); desc=f"Card settlement — {self.card.get('card_name','')}"; gid=str(uuid.uuid4())
        self.tx_repo.create(tx_date=today,account_id=src_id,pay_method=method,tx_type="DEBIT",amount=amt,description=desc,transaction_kind="TRANSFER",transfer_group_id=gid,category="transfer",pf_category="internal_transfer")
        self.tx_repo.create(tx_date=today,account_id=self.card["account_id"],pay_method=method,tx_type="CREDIT",amount=amt,description=desc,transaction_kind="TRANSFER",transfer_group_id=gid,category="transfer",pf_category="internal_transfer")
        self.settled.emit(); QMessageBox.information(self,"Done",f"Settlement of {fmt_money(amt)} recorded."); self.accept()


# ═══════════════════════════════════════════════
# REMINDERS WIDGET (right pan)
# ═══════════════════════════════════════════════

class RemindersWidget(QWidget):
    def __init__(self, cards_repo, parent=None):
        super().__init__(parent); self.cr=cards_repo; self.setStyleSheet("background:transparent;")
        self.lay=QVBoxLayout(self); self.lay.setContentsMargins(0,0,0,0); self.lay.setSpacing(8)
    def load_reminders(self, cards):
        while self.lay.count():
            itm=self.lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()
        title=QLabel("⏰  Reminders & Due Dates"); title.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:700;"); self.lay.addWidget(title)
        today=date.today(); reminders=[]
        for card in cards:
            name=card.get("card_name",card.get("issuer_bank","Card")); bd=card.get("billing_day",1)
            try:
                nb=today.replace(day=min(bd,28))
                if nb<=today:
                    if today.month==12: nb=nb.replace(year=today.year+1,month=1)
                    else: nb=nb.replace(month=today.month+1)
                du=(nb-today).days; col="#4F46E5" if du>5 else "#F59E0B"
                reminders.append((du,f"📅 {name} — Statement {nb.strftime('%d %b')}",col))
            except: pass
            cycle=self.cr.latest_cycle(card["account_id"])
            if cycle and cycle.get("due_date"):
                try:
                    due=date.fromisoformat(cycle["due_date"]); dd=(due-today).days; total=cycle.get("total_due",0)
                    if dd>=0: col="#EF4444" if dd<=3 else("#F59E0B" if dd<=7 else "#10B981"); reminders.append((dd,f"💰 {name} — Due {due.strftime('%d %b')} ({fmt_money(total)})",col))
                    else: reminders.append((-1,f"🚨 {name} — OVERDUE {abs(dd)}d ({fmt_money(total)})","#EF4444"))
                except: pass
        reminders.sort(key=lambda r:r[0])
        if not reminders: lbl=QLabel("No upcoming reminders."); lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;"); self.lay.addWidget(lbl)
        else:
            for _,text,color in reminders[:15]:
                row=QFrame(); row.setStyleSheet(f"background:{C['surface']};border:1px solid {C['border2']};border-radius:8px;padding:8px 12px;")
                rl=QHBoxLayout(row); rl.setContentsMargins(8,6,8,6)
                dot=QLabel("●"); dot.setStyleSheet(f"color:{color};font-size:8px;"); dot.setFixedWidth(12); rl.addWidget(dot)
                lbl=QLabel(text); lbl.setStyleSheet(f"color:{C['text']};font-size:12px;"); rl.addWidget(lbl,1); self.lay.addWidget(row)
        self.lay.addStretch()


# ═══════════════════════════════════════════════
# MAIN CARDS TAB
# ═══════════════════════════════════════════════

class CardsTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db=db; self.cr=repos["cards"]; self.acct=repos["accounts"]
        self.tx_repo=repos["transactions"]; self.bal=services["balance"]
        self._selected_card=None; self._build()

    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(28,16,28,16); root.setSpacing(10)
        hr=QHBoxLayout(); hr.setSpacing(12)
        h=QLabel("💳  Credit Cards"); h.setStyleSheet("font-size:24px;font-weight:800;color:#111827;"); hr.addWidget(h); hr.addStretch()
        ab=QPushButton("＋  Add Card"); ab.setObjectName("primary"); ab.setMinimumHeight(38); ab.setCursor(Qt.PointingHandCursor); ab.clicked.connect(self._add_card); hr.addWidget(ab)
        root.addLayout(hr)

        splitter=QSplitter(Qt.Horizontal); splitter.setStyleSheet("QSplitter{background:transparent;border:none;}")

        # LEFT PAN — tabs + carousel FIXED on top, details SCROLLABLE below
        left=QWidget(); left_lay=QVBoxLayout(left); left_lay.setContentsMargins(0,0,0,0); left_lay.setSpacing(0)
        fixed_top=QWidget(); ft_lay=QVBoxLayout(fixed_top); ft_lay.setContentsMargins(0,0,0,8); ft_lay.setSpacing(8)
        tabs_row=QHBoxLayout(); tabs_row.setSpacing(8)
        self.tab_active=QPushButton("✅  Active Cards"); self.tab_inactive=QPushButton("⏸  Closed Cards")
        self._sub_btns=[self.tab_active,self.tab_inactive]
        for b in self._sub_btns: b.setMinimumHeight(32); b.setCursor(Qt.PointingHandCursor)
        self.tab_active.clicked.connect(lambda:self._switch_sub(0)); self.tab_inactive.clicked.connect(lambda:self._switch_sub(1))
        for b in self._sub_btns: tabs_row.addWidget(b)
        tabs_row.addStretch(); ft_lay.addLayout(tabs_row)
        self.carousel=CarouselView([]); self.carousel.setMinimumHeight(200); self.carousel.setMaximumHeight(240)
        self.carousel.card_clicked.connect(self._on_card_clicked); ft_lay.addWidget(self.carousel)
        left_lay.addWidget(fixed_top)  # FIXED — does not scroll

        # Scrollable details area
        self.details_scroll=QScrollArea(); self.details_scroll.setWidgetResizable(True)
        self.details_scroll.setFrameShape(QFrame.NoFrame); self.details_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self.details_container=QWidget(); self.details_container.setStyleSheet("background:transparent;"); self.details_container.hide()
        self.details_lay=QVBoxLayout(self.details_container); self.details_lay.setContentsMargins(0,0,0,0); self.details_lay.setSpacing(12)
        self.details_scroll.setWidget(self.details_container)
        left_lay.addWidget(self.details_scroll, 1)  # STRETCH — scrollable
        splitter.addWidget(left)

        # RIGHT PAN — Reminders (minimum width 280)
        right=QWidget(); right.setMinimumWidth(280)
        right_lay=QVBoxLayout(right); right_lay.setContentsMargins(8,0,0,0); right_lay.setSpacing(0)
        self.reminders=RemindersWidget(self.cr)
        rem_scroll=QScrollArea(); rem_scroll.setWidgetResizable(True); rem_scroll.setFrameShape(QFrame.NoFrame)
        rem_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}"); rem_scroll.setWidget(self.reminders)
        right_lay.addWidget(rem_scroll)
        splitter.addWidget(right)
        splitter.setStretchFactor(0,3); splitter.setStretchFactor(1,1)
        root.addWidget(splitter,1)
        self._switch_sub(0)

    def _switch_sub(self, idx):
        for i,b in enumerate(self._sub_btns): b.setStyleSheet(_tab_btn_active() if i==idx else _tab_btn_inactive())
        self._selected_card=None; self.details_container.hide(); self._load_cards()

    def _utils(self, cards):
        u={}
        for card in cards:
            aid=card["account_id"]; lim=card.get("credit_limit",0) or card.get("acct_limit",0)
            u[aid]=min(abs(self.bal.get_balance(aid))/lim,1.0) if lim>0 else 0.0
        return u

    def _load_cards(self):
        ac=self.cr.list_active()
        ic=[dict(r) for r in self.db.execute("SELECT c.*,a.display_name AS acct_name,a.credit_limit AS acct_limit FROM cards c JOIN accounts a ON a.account_id=c.account_id WHERE c.is_active=0 ORDER BY c.sort_order").fetchall()]
        active_idx=0 if self._sub_btns[0].styleSheet()==_tab_btn_active() else 1
        cards=ac if active_idx==0 else ic
        self.carousel.load_cards(cards,self._utils(cards))
        self.reminders.load_reminders(ac)

    def _on_card_clicked(self, card_id):
        card=self.cr.get(card_id)
        if not card: return
        self._selected_card=card; self._show_details(card)

    def _show_details(self, card):
        while self.details_lay.count():
            itm=self.details_lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()
        aid=card["account_id"]
        limit=card.get("credit_limit",0) or card.get("acct_limit",0)
        balance=abs(self.bal.get_balance(aid))
        util=(balance/limit*100) if limit>0 else 0
        cycle=self.cr.latest_cycle(aid)
        c1=card.get("card_color_1","#3a3a3a"); c2=card.get("card_color_2","#0f0f0f")

        # ── Header: card name with card gradient style ──
        hdr=QFrame()
        hdr.setStyleSheet(f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {c1},stop:1 {c2});border-radius:12px;}}QLabel{{background:transparent;}}")
        hdr_lay=QHBoxLayout(hdr); hdr_lay.setContentsMargins(20,12,20,12)
        name_lbl=QLabel(f"<b style='font-size:16px;color:white;'>{card.get('card_name','Card')}</b>")
        hdr_lay.addWidget(name_lbl); hdr_lay.addStretch()
        net_lbl=QLabel(f"<span style='color:rgba(255,255,255,0.7);font-size:12px;'>{card.get('card_network','')} {card.get('card_class','')}</span>")
        hdr_lay.addWidget(net_lbl)
        self.details_lay.addWidget(hdr)

        # ── KPI Box ──
        kpi=QFrame(); kpi.setStyleSheet(f"background:{C['surface']};border:1px solid {C['border2']};border-radius:10px;padding:12px;")
        kpi_lay=QHBoxLayout(kpi); kpi_lay.setSpacing(20); kpi_lay.setContentsMargins(12,8,12,8)
        stmt_date=card.get("statement_date","—") or "—"
        due_date=cycle.get("due_date","—") if cycle else "—"
        util_color="#EF4444" if util>70 else("#F59E0B" if util>30 else "#10B981")
        for label,value,color in [("Limit",fmt_money(limit),"#4F46E5"),("Statement",stmt_date,C['text']),("Due Date",due_date,"#EF4444"),("Utilized",f"{fmt_money(balance)} ({util:.0f}%)",util_color)]:
            col=QVBoxLayout(); col.setSpacing(2)
            ll=QLabel(label); ll.setStyleSheet(f"color:{C['text3']};font-size:10px;font-weight:600;")
            vl=QLabel(str(value)); vl.setStyleSheet(f"color:{color};font-size:15px;font-weight:800;")
            col.addWidget(ll); col.addWidget(vl); kpi_lay.addLayout(col)
        kpi_lay.addStretch(); self.details_lay.addWidget(kpi)

        # ── Transactions grouped by statement cycle ──
        txn_scroll=QScrollArea(); txn_scroll.setWidgetResizable(True); txn_scroll.setFrameShape(QFrame.NoFrame); txn_scroll.setMaximumHeight(350)
        txn_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        txn_inner=QWidget(); txn_inner.setStyleSheet("background:transparent;")
        txn_lay=QVBoxLayout(txn_inner); txn_lay.setSpacing(4); txn_lay.setContentsMargins(0,0,0,0)

        cycles=self.cr.get_cycles(aid)
        if cycles:
            for cyc in cycles:
                sd=cyc.get("cycle_start_date") or cyc.get("statement_date",""); ed=cyc.get("statement_date") or ""
                total=cyc.get("total_due",0)
                # Cycle utilization for this cycle
                cycle_txns=self.tx_repo.list_filters(account_id=aid,date_from=sd,date_to=ed,limit=500) if sd and ed else []
                cycle_spend=sum(t["amount"] for t in cycle_txns if t["tx_type"]=="DEBIT" and t.get("transaction_kind","REGULAR")=="REGULAR")
                cycle_util=(cycle_spend/limit*100) if limit>0 else 0
                cu_color="#EF4444" if cycle_util>70 else("#F59E0B" if cycle_util>30 else "#10B981")
                ch=QFrame(); ch.setStyleSheet(f"background:{C['surface2']};border:none;border-radius:8px;padding:6px 10px;")
                cl=QHBoxLayout(ch); cl.setContentsMargins(8,4,8,4)
                cl.addWidget(QLabel(f"<b>📅 {sd} → {ed}</b>"))
                cl.addStretch()
                cl.addWidget(QLabel(f"<span style='color:{cu_color};font-weight:700;'>{cycle_util:.0f}% utilized</span>"))
                cl.addWidget(QLabel(f"  Due: <b style='color:#EF4444'>{fmt_money(total)}</b>"))
                txn_lay.addWidget(ch)
                if cycle_txns:
                    for tx in cycle_txns: txn_lay.addWidget(_tx_card(tx))
                else:
                    nt=QLabel("No transactions."); nt.setStyleSheet(f"color:{C['text3']};font-size:11px;padding:6px;"); txn_lay.addWidget(nt)
        else:
            all_txns=self.tx_repo.list_filters(account_id=aid,limit=300)
            if all_txns:
                grouped=OrderedDict()
                for tx in sorted(all_txns,key=lambda t:t["tx_date"],reverse=True):
                    mk=tx["tx_date"][:7]
                    if mk not in grouped: grouped[mk]=[]
                    grouped[mk].append(tx)
                for mk,mtxns in grouped.items():
                    try: y,m=map(int,mk.split("-")); txn_lay.addWidget(_month_header(date(y,m,1).strftime("%B %Y")))
                    except: txn_lay.addWidget(_month_header(mk))
                    for tx in mtxns: txn_lay.addWidget(_tx_card(tx))
            else:
                nt=QLabel("No transactions found."); nt.setStyleSheet(f"color:{C['text3']};font-size:12px;"); txn_lay.addWidget(nt)
        txn_lay.addStretch(); txn_scroll.setWidget(txn_inner)
        self.details_lay.addWidget(txn_scroll,1)

        # ── Single settle button (fix 5: indigo text, not primary bg) ──
        settle_row=QHBoxLayout(); settle_row.addStretch()
        settle_btn=QPushButton("💰  Settle Bill")
        settle_btn.setStyleSheet(f"QPushButton{{background:transparent;color:{C['accent']};border:2px solid {C['accent']};border-radius:8px;padding:8px 24px;font-size:14px;font-weight:700;}}QPushButton:hover{{background:{C['accent']};color:white;}}")
        settle_btn.setMinimumHeight(38); settle_btn.setCursor(Qt.PointingHandCursor)
        settle_btn.clicked.connect(lambda:self._open_settle(card))
        settle_row.addWidget(settle_btn); self.details_lay.addLayout(settle_row)

        self.details_container.show()

    def _open_settle(self, card):
        dlg=SettlementDialog(card,self.cr,self.tx_repo,self.acct,self.bal,self)
        dlg.settled.connect(lambda:self._show_details(card)); dlg.exec_()

    def _add_card(self):
        dlg=AddCardDialog(self.cr,self.acct,self); dlg.card_added.connect(self.refresh); dlg.exec_()

    def refresh(self):
        self._selected_card=None; self.details_container.hide(); self._load_cards()
