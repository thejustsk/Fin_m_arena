"""Cards Tab — Professional credit card management with flip carousel."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QFrame, QStackedWidget, QDialog,
                              QFormLayout, QLineEdit, QComboBox, QSpinBox,
                              QDoubleSpinBox, QMessageBox, QSizePolicy,
                              QGraphicsView, QGraphicsScene, QGraphicsObject,
                              QScrollArea, QInputDialog, QGridLayout)
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

# ═══════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════

CARD_W = 320; CARD_H = 200; CARD_RADIUS = 16; GAP = 40
STRIPE_RECT = QRectF(-CARD_W / 2, -CARD_H / 2 + 20, CARD_W, 32)
EASE_FACTOR = 0.16; PX_PER_UNIT = CARD_W * 0.9; DRAG_THRESHOLD = 6

DEFAULT_GRADIENTS = [
    ("#3a3a3a", "#0f0f0f"), ("#1c3d5a", "#0a0f14"), ("#4b2e2e", "#120909"),
    ("#2e4b34", "#0a120c"), ("#3a2e4b", "#0f0a14"), ("#4b3a1a", "#120d05"),
    ("#1a3a3a", "#050f0f"), ("#4b1a3a", "#12050d"), ("#2a2a4b", "#08081b"),
    ("#4b3a2a", "#150f08"),
]

NETWORK_LOGOS = {
    "VISA": "VISA", "MASTERCARD": "MC", "RUPAY": "RuPay",
    "AMEX": "AMEX", "DINERS": "DINERS", "BAJAJ": "BAJAJ",
}

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

    def boundingRect(self):
        return QRectF(-CARD_W/2-2, -CARD_H/2-2, CARD_W+4, CARD_H+4)

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
        if h != self._stripe_hover:
            self._stripe_hover = h; self.setCursor(Qt.PointingHandCursor if h else Qt.ArrowCursor); self.update()
        super().hoverMoveEvent(e)

    def hoverLeaveEvent(self, e):
        if self._stripe_hover: self._stripe_hover = False; self.setCursor(Qt.ArrowCursor); self.update()
        super().hoverLeaveEvent(e)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = CARD_W, CARD_H; rect = QRectF(-w/2, -h/2, w, h)
        # Shadow
        painter.save(); painter.setPen(Qt.NoPen); painter.setBrush(QColor(0,0,0,110))
        painter.drawRoundedRect(QRectF(-w/2, -h/2+8, w, h), CARD_RADIUS, CARD_RADIUS); painter.restore()
        # Gradient
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
        # Bank name top-left
        painter.setPen(QColor(255,255,255,235)); f=QFont("Arial",13,QFont.Bold); f.setLetterSpacing(QFont.AbsoluteSpacing,0.6); painter.setFont(f)
        painter.drawText(QRectF(-w/2+20,-h/2+14,w-40,20), Qt.AlignLeft|Qt.AlignVCenter, self.data.get("issuer_bank","BANK"))
        # Brand
        brand = self.data.get("card_brand","")
        if brand:
            painter.setPen(QColor(255,255,255,170)); painter.setFont(QFont("Arial",10))
            painter.drawText(QRectF(-w/2+20,-h/2+34,w-40,16), Qt.AlignLeft|Qt.AlignVCenter, brand)
        # Chip
        cr = QRectF(-w/2+24,-13,34,26); cg=QLinearGradient(cr.topLeft(),cr.bottomLeft())
        cg.setColorAt(0,QColor("#f2f2f2")); cg.setColorAt(1,QColor("#999999"))
        painter.setPen(Qt.NoPen); painter.setBrush(cg); painter.drawRoundedRect(cr,4,4)
        painter.setPen(QPen(QColor("#777777"),1))
        for i in range(1,3): x=cr.left()+cr.width()*i/3; painter.drawLine(QPointF(x,cr.top()),QPointF(x,cr.bottom()))
        painter.drawLine(QPointF(cr.left(),cr.center().y()),QPointF(cr.right(),cr.center().y()))
        # Utilization bar full width
        bx=-w/2+20; by=22; bw=w-40; bh=14
        painter.setPen(Qt.NoPen); painter.setBrush(QColor(255,255,255,25)); painter.drawRoundedRect(QRectF(bx,by,bw,bh),4,4)
        util=max(0.0,min(1.0,self._utilization)); fw=bw*util
        bc = QColor("#10B981") if util<0.3 else (QColor("#F59E0B") if util<0.7 else QColor("#EF4444"))
        if fw>0: painter.setBrush(bc); painter.drawRoundedRect(QRectF(bx,by,fw,bh),4,4)
        painter.setPen(QColor(255,255,255,200)); painter.setFont(QFont("Arial",7,QFont.Bold))
        painter.drawText(QRectF(bx,by,bw,bh), Qt.AlignCenter, f"{util*100:.0f}% utilized")
        # Network bottom-right
        painter.setPen(QColor(255,255,255,235)); tf=QFont("Arial",14,QFont.Bold); tf.setItalic(True); tf.setLetterSpacing(QFont.AbsoluteSpacing,1.0); painter.setFont(tf)
        painter.drawText(QRectF(-w/2,h/2-52,w-20,22), Qt.AlignRight|Qt.AlignVCenter, self.data.get("card_network","VISA"))
        cls=self.data.get("card_class","")
        if cls: painter.setPen(QColor(255,255,255,150)); painter.setFont(QFont("Arial",10))
        painter.drawText(QRectF(-w/2,h/2-32,w-20,18), Qt.AlignRight|Qt.AlignVCenter, cls)

    def _draw_back(self, painter):
        w, h = CARD_W, CARD_H
        sc = QColor(35,35,35,235) if self._stripe_hover else QColor(0,0,0,220)
        painter.setPen(Qt.NoPen); painter.setBrush(sc); painter.drawRect(STRIPE_RECT)
        painter.setPen(QColor(255,255,255,220 if self._stripe_hover else 150))
        painter.setFont(QFont("Arial",9,QFont.DemiBold))
        painter.drawText(STRIPE_RECT, Qt.AlignCenter, "VIEW CARD DETAILS  \u2192" if self._stripe_hover else "VIEW CARD DETAILS")
        # Cardholder
        painter.setPen(QColor(255,255,255,200)); painter.setFont(QFont("Arial",11))
        painter.drawText(QRectF(-w/2+20,h/2-80,w-40,20), Qt.AlignLeft|Qt.AlignVCenter, self.data.get("cardholder_name","CARDHOLDER"))
        # Card number
        mono=QFont("Courier New",11,QFont.DemiBold); painter.setFont(mono); painter.setPen(QColor(255,255,255,235))
        number = self.data.get("card_number","")
        if not number: number = f"XXXX  XXXX  XXXX  {self.data.get('last_four','0000')}"
        fm=painter.fontMetrics(); mw=w-40
        if fm.horizontalAdvance(number)>mw:
            while fm.horizontalAdvance(number)>mw and len(number)>4: number=number[:-1]
        painter.drawText(QRectF(-w/2+20,h/2-56,w-40,20), Qt.AlignLeft|Qt.AlignVCenter, number)
        # Valid
        painter.setFont(QFont("Courier New",9)); painter.setPen(QColor(255,255,255,170))
        em=self.data.get("expiry_month",12); ey=self.data.get("expiry_year",2028)
        painter.drawText(QRectF(-w/2+20,h/2-34,w-40,20), Qt.AlignLeft|Qt.AlignVCenter, f"Valid: {em:02d}/{str(ey)[-2:]}")


# ═══════════════════════════════════════════════
# CAROUSEL VIEW
# ═══════════════════════════════════════════════

class CarouselView(QGraphicsView):
    card_selected = pyqtSignal(str)
    def __init__(self, cards_data=None, utilizations=None, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setStyleSheet("background-color:#111827;border:none;border-radius:16px;")
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
            item=CardItem(data,i,u); item.stripe_clicked.connect(self.card_selected.emit)
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
        self._press_pos=e.pos(); self._press_item=self.itemAt(e.pos())
        self._dragging=False; self._drag_start_progress=self.target_progress; super().mousePressEvent(e)
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
                if item.show_back and STRIPE_RECT.contains(lp): self.card_selected.emit(item.data.get("card_id",""))
                else: item.flip()
        self._dragging=False; self._press_pos=None; self._press_item=None; super().mouseReleaseEvent(e)
    def wheelEvent(self, e): self.target_progress-=e.angleDelta().y()/240.0; e.accept()
    def keyPressEvent(self, e):
        if e.key()==Qt.Key_Left: self.target_progress=round(self.target_progress)-1
        elif e.key()==Qt.Key_Right: self.target_progress=round(self.target_progress)+1
        elif e.key()==Qt.Key_Space:
            nearest=min(self.items,key=lambda it:abs(((it.index-self.progress+self.card_count/2)%self.card_count)-self.card_count/2))
            nearest.flip()
        else: super().keyPressEvent(e)
    def resizeEvent(self, e): self.scene.setSceneRect(0,0,self.viewport().width(),self.viewport().height()); super().resizeEvent(e)


# ═══════════════════════════════════════════════
# PREVIEW WIDGETS (no utilization bar)
# ═══════════════════════════════════════════════

class CardPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setFixedSize(CARD_W, CARD_H)
        self._data = {"issuer_bank":"BANK","card_brand":"","card_network":"VISA","card_class":"","last_four":"0000","expiry_month":12,"expiry_year":2028,"card_color_1":"#3a3a3a","card_color_2":"#0f0f0f"}
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
        network=self._data.get("card_network","VISA"); p.setPen(QColor(255,255,255,235))
        tf=QFont("Arial",14,QFont.Bold); tf.setItalic(True); p.setFont(tf)
        p.drawText(QRectF(0,h-52,w-20,22),Qt.AlignRight|Qt.AlignVCenter,network)
        cls=self._data.get("card_class","")
        if cls: p.setPen(QColor(255,255,255,150)); p.setFont(QFont("Arial",10)); p.drawText(QRectF(0,h-32,w-20,18),Qt.AlignRight|Qt.AlignVCenter,cls)
        pen=QPen(QColor(255,255,255,40)); pen.setWidth(1); p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect.adjusted(0.5,0.5,-0.5,-0.5),CARD_RADIUS,CARD_RADIUS); p.end()

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
        name=self._data.get("cardholder_name","CARDHOLDER")
        p.setPen(QColor(255,255,255,200)); p.setFont(QFont("Arial",11)); p.drawText(QRectF(20,h-80,w-40,20),Qt.AlignLeft|Qt.AlignVCenter,name)
        last4=self._data.get("last_four","0000")
        p.setPen(QColor(255,255,255,235)); p.setFont(QFont("Courier New",11,QFont.DemiBold))
        p.drawText(QRectF(20,h-56,w-40,20),Qt.AlignLeft|Qt.AlignVCenter,f"XXXX  XXXX  XXXX  {last4}")
        em=self._data.get("expiry_month",12); ey=self._data.get("expiry_year",2028)
        p.setPen(QColor(255,255,255,170)); p.setFont(QFont("Courier New",9))
        p.drawText(QRectF(20,h-34,w-40,20),Qt.AlignLeft|Qt.AlignVCenter,f"Valid: {em:02d}/{str(ey)[-2:]}")
        pen=QPen(QColor(255,255,255,40)); pen.setWidth(1); p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect.adjusted(0.5,0.5,-0.5,-0.5),CARD_RADIUS,CARD_RADIUS); p.end()


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
        self.billing_day=QSpinBox(); self.billing_day.setRange(1,28); self.billing_day.setValue(1); form.addRow("Billing Day",self.billing_day)
        self.grace_days=QSpinBox(); self.grace_days.setRange(0,55); self.grace_days.setValue(20); form.addRow("Grace Period (days)",self.grace_days)
        self.annual_fee=QDoubleSpinBox(); self.annual_fee.setRange(0,99999); self.annual_fee.setPrefix("₹ "); self.annual_fee.setDecimals(0); form.addRow("Annual Fee",self.annual_fee)
        self.color_idx=QComboBox()
        for i in range(len(DEFAULT_GRADIENTS)): self.color_idx.addItem(f"Style {i+1}")
        self.color_idx.currentIndexChanged.connect(self._upd); form.addRow("Card Style",self.color_idx)
        fc.addLayout(form)
        br=QHBoxLayout(); br.addStretch()
        c=QPushButton("Cancel"); c.clicked.connect(self.reject); br.addWidget(c)
        a=QPushButton("  Add Card  "); a.setObjectName("primary"); a.clicked.connect(self._save); br.addWidget(a)
        fc.addLayout(br); lay.addLayout(fc)
        # Previews
        pc=QVBoxLayout(); pc.setSpacing(8)
        fl=QLabel("Front"); fl.setStyleSheet(f"color:{C['text2']};font-size:13px;font-weight:700;"); pc.addWidget(fl)
        self.preview=CardPreviewWidget(); pc.addWidget(self.preview)
        bl=QLabel("Back"); bl.setStyleSheet(f"color:{C['text2']};font-size:13px;font-weight:700;"); pc.addWidget(bl)
        self.back_preview=CardBackPreviewWidget(); pc.addWidget(self.back_preview)
        pc.addStretch(); lay.addLayout(pc)

    def _upd(self):
        c1,c2=DEFAULT_GRADIENTS[self.color_idx.currentIndex()]
        d=dict(issuer_bank=self.issuer.text().strip() or "BANK",card_brand=self.brand.text().strip(),card_network=self.network.currentText(),card_class=self.card_class.text().strip(),cardholder_name=self.cardholder.text().strip() or "CARDHOLDER",last_four=self.last_four.text().strip() or "0000",expiry_month=self.expiry_month.value(),expiry_year=self.expiry_year.value(),card_color_1=c1,card_color_2=c2)
        self.preview.update_data(**d); self.back_preview.update_data(**d)

    def _save(self):
        name=self.card_name.text().strip(); bank=self.issuer.text().strip(); limit=self.credit_limit.value()
        if not name or not bank or limit<=0: QMessageBox.warning(self,"Missing","Card name, bank, and credit limit required."); return
        existing=None
        for a in self.acct.list_active():
            if a["display_name"].upper()==bank.upper(): existing=a; break
        if existing: aid=existing["account_id"]
        else:
            aid=str(uuid.uuid4())
            self.acct.create(account_id=aid,display_name=bank,short_label=bank[:8].upper(),account_type="CREDIT_CARD",credit_limit=limit,opening_balance=0,color_hex="#7C3AED")
        c1,c2=DEFAULT_GRADIENTS[self.color_idx.currentIndex()]
        self.cr.create(account_id=aid,card_name=name,last_four=self.last_four.text().strip() or "0000",card_network=self.network.currentText(),card_type=self.card_class.text().strip() or "PERSONAL",card_class=self.card_class.text().strip(),card_brand=self.brand.text().strip(),issuer_bank=bank,cardholder_name=self.cardholder.text().strip() or name.upper(),expiry_month=self.expiry_month.value(),expiry_year=self.expiry_year.value(),billing_day=self.billing_day.value(),grace_days=self.grace_days.value(),annual_fee=self.annual_fee.value(),card_color_1=c1,card_color_2=c2)
        self.card_added.emit(); self.accept()


# ═══════════════════════════════════════════════
# CARD DETAILS DIALOG — full redesign
# ═══════════════════════════════════════════════

class CardDetailsDialog(QDialog):
    settled = pyqtSignal()
    def __init__(self, card, cards_repo, tx_repo, accounts_repo, bal_svc, parent=None):
        super().__init__(parent)
        self.card=card; self.cr=cards_repo; self.tx_repo=tx_repo; self.acct=accounts_repo; self.bal=bal_svc
        self.setWindowTitle(f"Card — {card.get('card_name','Details')}"); self.setMinimumWidth(700); self.setMinimumHeight(600)
        self.setStyleSheet(f"QDialog{{background:{C['bg']};}}"); self._build()

    def _build(self):
        main=QVBoxLayout(self); main.setContentsMargins(0,0,0,0); main.setSpacing(0)
        # Header
        hdr=QFrame(); hdr.setStyleSheet("background:#4F46E5;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(24,14,24,14)
        title=QLabel(f"💳  {self.card.get('card_name','Card')}"); title.setStyleSheet("color:white;font-size:20px;font-weight:800;background:transparent;")
        hl.addWidget(title); hl.addStretch()
        bl=QLabel(self.card.get("issuer_bank","")); bl.setStyleSheet("color:rgba(255,255,255,0.7);font-size:13px;background:transparent;"); hl.addWidget(bl)
        main.addWidget(hdr)
        # Scroll
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner=QWidget(); inner.setStyleSheet("background:transparent;")
        lay=QVBoxLayout(inner); lay.setContentsMargins(24,16,24,16); lay.setSpacing(16)

        limit=self.card.get("credit_limit",0) or self.card.get("acct_limit",0)
        balance=abs(self.bal.get_balance(self.card["account_id"]))
        util=(balance/limit*100) if limit>0 else 0
        em=self.card.get("expiry_month",0); ey=self.card.get("expiry_year",0)

        # KPI Box
        kpi=QFrame(); kpi.setStyleSheet(f"background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;padding:16px;")
        kl=QGridLayout(kpi); kl.setSpacing(8); kl.setContentsMargins(16,14,16,14)
        fields=[("Card Name",self.card.get("card_name","—")),("Bank",self.card.get("issuer_bank","—")),("Co-Brand",self.card.get("card_brand","—") or "—"),("Network",self.card.get("card_network","—")),("Class",self.card.get("card_class","—") or "—"),("Last 4 Digits",f"•••• {self.card.get('last_four','0000')}"),("Cardholder",self.card.get("cardholder_name","—")),("Valid Till",f"{em:02d}/{ey}"),("Billing Day",f"Every {self.card.get('billing_day',1)}th"),("Statement Date",self.card.get("statement_date","—") or "—"),("Grace Period",f"{self.card.get('grace_days',20)} days"),("Credit Limit",fmt_money(limit)),("Annual Fee",fmt_money(self.card.get("annual_fee",0))),("Interest",f"{self.card.get('interest_rate',3.5)}% p.m."),("Rewards",self.card.get("reward_program","—") or "—"),("Outstanding",fmt_money(balance))]
        for i,(label,value) in enumerate(fields):
            r,c=divmod(i,4)
            ll=QLabel(label); ll.setStyleSheet(f"color:{C['text3']};font-size:10px;font-weight:600;"); kl.addWidget(ll,r*2,c)
            vl=QLabel(str(value)); vl.setStyleSheet(f"color:{C['text']};font-size:12px;font-weight:700;"); kl.addWidget(vl,r*2+1,c)
        lay.addWidget(kpi)

        # Utilization bar
        uf=QFrame(); uf.setStyleSheet(f"background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;padding:14px 16px;")
        ul=QVBoxLayout(uf); ul.setSpacing(6)
        uh=QHBoxLayout(); uh.addWidget(QLabel("<b>Utilization</b>")); uh.addStretch()
        uc="#10B981" if util<30 else("#F59E0B" if util<70 else "#EF4444")
        uh.addWidget(QLabel(f"<b style='color:{uc}'>{util:.1f}%</b>")); ul.addLayout(uh)
        bar=QFrame(); bar.setFixedHeight(10); bar.setStyleSheet(f"background:{C['surface2']};border:none;border-radius:5px;")
        bl2=QHBoxLayout(bar); bl2.setContentsMargins(0,0,0,0); bl2.setSpacing(0)
        fill=QFrame(); fill.setFixedHeight(10); fill.setFixedWidth(max(1,int(600*util/100))); fill.setStyleSheet(f"background:{uc};border:none;border-radius:5px;")
        bl2.addWidget(fill); bl2.addStretch(); ul.addWidget(bar)
        avail=limit-balance
        ul.addWidget(QLabel(f"Available: <b>{fmt_money(max(avail,0))}</b>  |  Outstanding: <b>{fmt_money(balance)}</b>  |  Limit: <b>{fmt_money(limit)}</b>").setStyleSheet(f"color:{C['text3']};font-size:11px;"))
        lay.addWidget(uf)

        # Transactions by statement cycle
        tl=QLabel("Transactions by Statement Cycle"); tl.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:700;"); lay.addWidget(tl)
        cycles=self.cr.get_cycles(self.card["account_id"])
        aid=self.card["account_id"]
        if cycles:
            for cycle in cycles:
                sd=cycle.get("cycle_start_date") or cycle.get("statement_date",""); ed=cycle.get("statement_date") or ""
                total=cycle.get("total_due",0); minimum=cycle.get("minimum_due",0)
                ch=QFrame(); ch.setStyleSheet(f"background:{C['surface']};border:1px solid {C['border2']};border-radius:10px;padding:10px 14px;")
                cl2=QHBoxLayout(ch); cl2.setContentsMargins(10,8,10,8)
                cl2.addWidget(QLabel(f"<b>📅 {sd} → {ed}</b>")); cl2.addStretch()
                cl2.addWidget(QLabel(f"Due: <b style='color:#EF4444'>{fmt_money(total)}</b>"))
                cl2.addWidget(QLabel(f"  Min: <b style='color:#F59E0B'>{fmt_money(minimum)}</b>"))
                lay.addWidget(ch)
                txns=self.tx_repo.list_filters(account_id=aid,date_from=sd,date_to=ed,limit=200) if sd and ed else []
                if txns:
                    for tx in txns: lay.addWidget(_tx_card(tx))
                else: nt=QLabel("No transactions in this cycle."); nt.setStyleSheet(f"color:{C['text3']};font-size:11px;padding:8px;"); lay.addWidget(nt)
        else:
            all_txns=self.tx_repo.list_filters(account_id=aid,limit=500)
            if all_txns:
                grouped=OrderedDict()
                for tx in sorted(all_txns,key=lambda t:t["tx_date"],reverse=True):
                    mk=tx["tx_date"][:7]
                    if mk not in grouped: grouped[mk]=[]
                    grouped[mk].append(tx)
                for mk,mtxns in grouped.items():
                    try: y,m=map(int,mk.split("-")); lay.addWidget(_month_header(date(y,m,1).strftime("%B %Y")))
                    except: lay.addWidget(_month_header(mk))
                    for tx in mtxns: lay.addWidget(_tx_card(tx))
            else: nt=QLabel("No transactions found."); nt.setStyleSheet(f"color:{C['text3']};font-size:12px;"); lay.addWidget(nt)

        # Settlement bar
        settle=QFrame(); settle.setStyleSheet(f"background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;padding:16px;")
        sl=QVBoxLayout(settle); sl.setSpacing(10); sl.addWidget(QLabel("<b>💰  Settle Bill</b>"))
        cycle=self.cr.latest_cycle(aid)
        stmt_due=cycle.get("total_due",0) if cycle else 0
        min_due=cycle.get("minimum_due",0) if cycle else 0
        opt_row=QHBoxLayout(); opt_row.setSpacing(12)
        self.settle_opt=QComboBox()
        self.settle_opt.addItem(f"Current Outstanding — {fmt_money(balance)}",balance)
        self.settle_opt.addItem(f"Statement Outstanding — {fmt_money(stmt_due)}",stmt_due)
        self.settle_opt.addItem(f"Minimum Outstanding — {fmt_money(min_due)}",min_due)
        self.settle_opt.setMinimumHeight(34); opt_row.addWidget(self.settle_opt,1)
        opt_row.addWidget(QLabel("From:"))
        self.settle_src=QComboBox()
        for a in self.acct.list_active():
            if a["account_type"]!="CREDIT_CARD": self.settle_src.addItem(a["display_name"],a["account_id"])
        self.settle_src.setMinimumHeight(34); opt_row.addWidget(self.settle_src,1)
        opt_row.addWidget(QLabel("Method:"))
        self.settle_method=QComboBox(); self.settle_method.addItems(PAYMENT_METHODS); self.settle_method.setMinimumHeight(34); opt_row.addWidget(self.settle_method)
        sl.addLayout(opt_row)
        rr=QHBoxLayout(); rr.addStretch()
        rb=QPushButton("💸  Repay"); rb.setObjectName("primary"); rb.setMinimumHeight(40); rb.setMinimumWidth(160); rb.setCursor(Qt.PointingHandCursor); rb.clicked.connect(self._repay); rr.addWidget(rb)
        sl.addLayout(rr); lay.addWidget(settle); lay.addStretch()
        scroll.setWidget(inner); main.addWidget(scroll,1)

    def _repay(self):
        amt=self.settle_opt.currentData(); src_id=self.settle_src.currentData(); method=self.settle_method.currentText()
        if not amt or amt<=0: QMessageBox.warning(self,"Invalid","No outstanding amount to repay."); return
        if not src_id: QMessageBox.warning(self,"No Source","Select a source account."); return
        today=date.today().isoformat(); desc=f"Card settlement — {self.card.get('card_name','')}"; gid=str(uuid.uuid4())
        self.tx_repo.create(tx_date=today,account_id=src_id,pay_method=method,tx_type="DEBIT",amount=amt,description=desc,transaction_kind="TRANSFER",transfer_group_id=gid,category="transfer",pf_category="internal_transfer")
        self.tx_repo.create(tx_date=today,account_id=self.card["account_id"],pay_method=method,tx_type="CREDIT",amount=amt,description=desc,transaction_kind="TRANSFER",transfer_group_id=gid,category="transfer",pf_category="internal_transfer")
        self.settled.emit(); QMessageBox.information(self,"Done",f"Settlement of {fmt_money(amt)} recorded."); self.accept()


# ═══════════════════════════════════════════════
# REMINDERS WIDGET
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
            name=card.get("card_name",card.get("issuer_bank","Card")); bd=card.get("billing_day",1); gd=card.get("grace_days",20)
            try:
                nb=today.replace(day=min(bd,28))
                if nb<=today:
                    if today.month==12: nb=nb.replace(year=today.year+1,month=1)
                    else: nb=nb.replace(month=today.month+1)
                du=(nb-today).days; col="#4F46E5" if du>5 else "#F59E0B"
                reminders.append((du,f"📅 {name} — Statement on {nb.strftime('%d %b')}",col))
            except: pass
            cycle=self.cr.latest_cycle(card["account_id"])
            if cycle and cycle.get("due_date"):
                try:
                    due=date.fromisoformat(cycle["due_date"]); dd=(due-today).days; total=cycle.get("total_due",0)
                    if dd>=0: col="#EF4444" if dd<=3 else("#F59E0B" if dd<=7 else "#10B981"); reminders.append((dd,f"💰 {name} — Due {due.strftime('%d %b')} ({fmt_money(total)})",col))
                    else: reminders.append((-1,f"🚨 {name} — OVERDUE by {abs(dd)} days ({fmt_money(total)})","#EF4444"))
                except: pass
        reminders.sort(key=lambda r:r[0])
        if not reminders: lbl=QLabel("No upcoming reminders."); lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;"); self.lay.addWidget(lbl)
        else:
            for _,text,color in reminders[:12]:
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
        self.db=db; self.cr=repos["cards"]; self.acct=repos["accounts"]; self.tx_repo=repos["transactions"]; self.bal=services["balance"]; self._build()

    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(28,16,28,16); root.setSpacing(10)
        hr=QHBoxLayout(); hr.setSpacing(12)
        h=QLabel("💳  Credit Cards"); h.setStyleSheet("font-size:24px;font-weight:800;color:#111827;"); hr.addWidget(h); hr.addStretch()
        ab=QPushButton("＋  Add Card"); ab.setObjectName("primary"); ab.setMinimumHeight(38); ab.setCursor(Qt.PointingHandCursor); ab.clicked.connect(self._add_card); hr.addWidget(ab)
        root.addLayout(hr)
        tr=QHBoxLayout(); tr.setSpacing(8)
        self.tab_active=QPushButton("✅  Active Cards"); self.tab_inactive=QPushButton("⏸  Inactive Cards")
        self._sub_btns=[self.tab_active,self.tab_inactive]
        for b in self._sub_btns: b.setMinimumHeight(34); b.setCursor(Qt.PointingHandCursor)
        self.tab_active.clicked.connect(lambda:self._switch_sub(0)); self.tab_inactive.clicked.connect(lambda:self._switch_sub(1))
        for b in self._sub_btns: tr.addWidget(b)
        tr.addStretch(); root.addLayout(tr)
        self.stack=QStackedWidget(); self.stack.addWidget(self._build_sub(True)); self.stack.addWidget(self._build_sub(False))
        root.addWidget(self.stack,1); self._switch_sub(0)

    def _build_sub(self, active):
        w=QWidget(); lay=QVBoxLayout(w); lay.setContentsMargins(0,0,0,0); lay.setSpacing(10)
        c=CarouselView([]); c.setMinimumHeight(240); c.setMaximumHeight(280); c.card_selected.connect(self._show_details); lay.addWidget(c)
        r=RemindersWidget(self.cr); s=QScrollArea(); s.setWidgetResizable(True); s.setFrameShape(QFrame.NoFrame); s.setStyleSheet("QScrollArea{background:transparent;border:none;}"); s.setWidget(r); lay.addWidget(s,1)
        if active: self._ac=c; self._ar=r
        else: self._ic=c; self._ir=r
        return w

    def _switch_sub(self, idx):
        self.stack.setCurrentIndex(idx)
        for i,b in enumerate(self._sub_btns): b.setStyleSheet(_tab_btn_active() if i==idx else _tab_btn_inactive())
        self._load_cards()

    def _utils(self, cards):
        u={}
        for card in cards:
            aid=card["account_id"]; lim=card.get("credit_limit",0) or card.get("acct_limit",0)
            u[aid]=min(abs(self.bal.get_balance(aid))/lim,1.0) if lim>0 else 0.0
        return u

    def _load_cards(self):
        ac=self.cr.list_active()
        ic=[dict(r) for r in self.db.execute("SELECT c.*,a.display_name AS acct_name,a.credit_limit AS acct_limit FROM cards c JOIN accounts a ON a.account_id=c.account_id WHERE c.is_active=0 ORDER BY c.sort_order").fetchall()]
        if self.stack.currentIndex()==0: self._ac.load_cards(ac,self._utils(ac)); self._ar.load_reminders(ac)
        else: self._ic.load_cards(ic,self._utils(ic)); self._ir.load_reminders(ic)

    def _add_card(self):
        dlg=AddCardDialog(self.cr,self.acct,self); dlg.card_added.connect(self.refresh); dlg.exec_()

    def _show_details(self, card_id):
        card=self.cr.get(card_id)
        if not card: return
        dlg=CardDetailsDialog(card,self.cr,self.tx_repo,self.acct,self.bal,self)
        dlg.settled.connect(self._load_cards); dlg.exec_()

    def refresh(self): self._load_cards()
