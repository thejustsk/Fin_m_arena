"""Debit Cards Tab — Same carousel pattern as Credit Cards, fully independent."""
from collections import OrderedDict
from datetime import date, datetime

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QFrame, QDialog,
                              QFormLayout, QLineEdit, QComboBox, QSpinBox,
                              QDoubleSpinBox, QMessageBox, QScrollArea,
                              QSizePolicy, QGraphicsView, QGraphicsScene,
                              QGraphicsObject)
from PyQt5.QtCore import (Qt, pyqtSignal, QDate, QSize, QRect, QPoint,
                           QRectF, QPointF, QTimer, QPropertyAnimation,
                           QEasingCurve, pyqtProperty)
from PyQt5.QtGui import (QCursor, QPainter, QColor, QLinearGradient, QFont,
                          QPen, QTransform)

from ui.theme import C
from ui.sidebar import fmt_money
from ui.tabs.database_tab import _tx_card, _day_header
import sip
import uuid


# ═══════════════════════════════════════════════
# CONSTANTS (independent from CC tab)
# ═══════════════════════════════════════════════
DC_CARD_W = 320; DC_CARD_H = 200; DC_CARD_RADIUS = 16; DC_GAP = 40
DC_STRIPE_RECT = QRectF(-DC_CARD_W/2, -DC_CARD_H/2+20, DC_CARD_W, 32)
DC_EASE = 0.16; DC_PX_PER = DC_CARD_W * 0.9; DC_DRAG_TH = 6

DC_GRADIENTS = [
    ("#b8bcc2", "#5f656d"),  # Silver Steel
    ("#8a9199", "#2f343b"),  # Gunmetal
    ("#d9d9d6", "#7d7d79"),  # Platinum
    ("#c9ced3", "#59616b"),  # Titanium
    ("#b79a67", "#4e3c1f"),  # Antique Gold
    ("#d0a85d", "#6a4b17"),  # Brushed Gold
    ("#b56d43", "#59301c"),  # Copper
    ("#9f7554", "#4d2e1e"),  # Bronze
    ("#8b8e91", "#242629"),  # Iron
    ("#707780", "#1e2328"),  # Graphite
    ("#bcc3cb", "#40464d"),  # Chrome
    ("#6d747d", "#2a2d31"),  # Carbon Steel
    ("#9da3a8", "#4f555b"),  # Pewter
    ("#7b8088", "#34383d"),  # Nickel
    ("#8f8c88", "#4c4844"),  # Zinc
    ("#d4d0c8", "#666057"),  # Palladium
    ("#8d8173", "#43382f"),  # Raw Steel
    ("#c0b8aa", "#5a544d"),  # Satin Alloy
    ("#6e7377", "#17191b"),  # Black Chrome
    ("#e3d8b8", "#7b6b43"),  # Champagne Metal
]
DC_GRAD_NAMES = [
    "Titanium",
    "Gunmetal",
    "Platinum",
    "Silverforge",
    "Aurum",
    "Bullion",
    "Copperline",
    "Bronzework",
    "Ironclad",
    "Graphite",
    "Chrome",
    "Carbon",
    "Pewter",
    "Nickel",
    "Zinc",
    "Palladium",
    "Forge",
    "Alloy",
    "Blacksteel",
    "Champagne",
]


def _dc_tab_active():
    return f"QPushButton{{background:{C['accent']};color:white;border:1px solid {C['accent']};border-radius:8px;padding:8px 16px;font-size:13px;font-weight:700;}}"
def _dc_tab_inactive():
    return f"QPushButton{{background:{C['surface']};color:{C['text2']};border:1px solid {C['border']};border-radius:8px;padding:8px 16px;font-size:13px;font-weight:600;}}QPushButton:hover{{border-color:{C['accent']};color:{C['accent']};}}"


def _dc_smoothstep(t):
    t = max(0.0, min(1.0, t)); return t*t*(3-2*t)


# ═══════════════════════════════════════════════
# CARD ITEM (exact copy from CC tab, independent)
# ═══════════════════════════════════════════════

class DCCardItem(QGraphicsObject):
    stripe_clicked = pyqtSignal(str)
    def __init__(self, card_data, index, parent=None):
        super().__init__()
        self.data = card_data; self.index = index; self.show_back = False
        self._flip_scale = 1.0; self._anim = None; self._stripe_hover = False
        self.setAcceptHoverEvents(True)
    def getFlipScale(self): return self._flip_scale
    def setFlipScale(self, v): self._flip_scale = v; self.update()
    flipScale = pyqtProperty(float, getFlipScale, setFlipScale)
    def boundingRect(self): return QRectF(-DC_CARD_W/2-2, -DC_CARD_H/2-2, DC_CARD_W+4, DC_CARD_H+4)
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
        h = self.show_back and DC_STRIPE_RECT.contains(e.pos())
        if h != self._stripe_hover: self._stripe_hover = h; self.setCursor(Qt.PointingHandCursor if h else Qt.ArrowCursor); self.update()
        super().hoverMoveEvent(e)
    def hoverLeaveEvent(self, e):
        if self._stripe_hover: self._stripe_hover = False; self.setCursor(Qt.ArrowCursor); self.update()
        super().hoverLeaveEvent(e)
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = DC_CARD_W, DC_CARD_H; rect = QRectF(-w/2, -h/2, w, h)
        painter.save(); painter.setPen(Qt.NoPen); painter.setBrush(QColor(0,0,0,110))
        painter.drawRoundedRect(QRectF(-w/2, -h/2+8, w, h), DC_CARD_RADIUS, DC_CARD_RADIUS); painter.restore()
        g = QLinearGradient(-w/2, -h/2, w/2, h/2)
        g.setColorAt(0, QColor(self.data.get("card_color_1","#3a3a3a")))
        g.setColorAt(1, QColor(self.data.get("card_color_2","#0f0f0f")))
        painter.setPen(Qt.NoPen); painter.setBrush(g); painter.drawRoundedRect(rect, DC_CARD_RADIUS, DC_CARD_RADIUS)
        if not self.show_back: self._draw_front(painter)
        else: self._draw_back(painter)
        p = QPen(QColor(255,255,255,40)); p.setWidth(1); painter.setPen(p); painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5,0.5,-0.5,-0.5), DC_CARD_RADIUS, DC_CARD_RADIUS)
    def _draw_front(self, painter):
        w, h = DC_CARD_W, DC_CARD_H
        painter.setPen(QColor(255,255,255,235)); f=QFont("Arial",13,QFont.Bold); f.setLetterSpacing(QFont.AbsoluteSpacing,0.6); painter.setFont(f)
        painter.drawText(QRectF(-w/2+20,-h/2+14,w-40,20), Qt.AlignLeft|Qt.AlignVCenter, self.data.get("card_name","Card"))
        brand = self.data.get("acct_name","")
        if brand: painter.setPen(QColor(255,255,255,170)); painter.setFont(QFont("Arial",10)); painter.drawText(QRectF(-w/2+20,-h/2+34,w-40,16), Qt.AlignLeft|Qt.AlignVCenter, brand)
        cr = QRectF(-w/2+24,-13,34,26); cg=QLinearGradient(cr.topLeft(),cr.bottomLeft()); cg.setColorAt(0,QColor("#f2f2f2")); cg.setColorAt(1,QColor("#999999"))
        painter.setPen(Qt.NoPen); painter.setBrush(cg); painter.drawRoundedRect(cr,4,4)
        painter.setPen(QPen(QColor("#777777"),1))
        for i in range(1,3): x=cr.left()+cr.width()*i/3; painter.drawLine(QPointF(x,cr.top()),QPointF(x,cr.bottom()))
        painter.drawLine(QPointF(cr.left(),cr.center().y()),QPointF(cr.right(),cr.center().y()))
        network=self.data.get("card_network","VISA")
        if network and network != "OTHER":
            painter.setPen(QColor(255,255,255,235)); tf=QFont("Arial",14,QFont.Bold); tf.setItalic(True); tf.setLetterSpacing(QFont.AbsoluteSpacing,1.0); painter.setFont(tf)
            painter.drawText(QRectF(-w/2,h/2-52,w-20,22), Qt.AlignRight|Qt.AlignVCenter, network)
        cls=self.data.get("card_class","")
        if cls: painter.setPen(QColor(255,255,255,150)); painter.setFont(QFont("Arial",10)); painter.drawText(QRectF(-w/2,h/2-32,w-20,18), Qt.AlignRight|Qt.AlignVCenter, cls)
    def _draw_back(self, painter):
        w, h = DC_CARD_W, DC_CARD_H
        sc = QColor(35,35,35,235) if self._stripe_hover else QColor(0,0,0,220)
        painter.setPen(Qt.NoPen); painter.setBrush(sc); painter.drawRect(DC_STRIPE_RECT)
        painter.setPen(QColor(255,255,255,220 if self._stripe_hover else 150))
        painter.setFont(QFont("Arial",9,QFont.DemiBold))
        painter.drawText(DC_STRIPE_RECT, Qt.AlignCenter, "VIEW ACCOUNT DETAILS  \u2192" if self._stripe_hover else "VIEW ACCOUNT DETAILS")
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
# CAROUSEL VIEW (exact copy from CC tab, independent)
# FIX 3: timer stops when hidden, starts when shown
# ═══════════════════════════════════════════════

class DCCarouselView(QGraphicsView):
    card_clicked = pyqtSignal(str)
    def __init__(self, cards_data=None, parent=None):
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
        self.timer=QTimer(self); self.timer.timeout.connect(self._on_tick)
        # Don't start timer here — start in showEvent
        if cards_data: self.load_cards(cards_data)
    def showEvent(self, e):
        """Start timer when carousel becomes visible."""
        super().showEvent(e)
        if self.card_count > 0:
            self.timer.start(16)
    def hideEvent(self, e):
        """Stop timer when carousel becomes hidden."""
        self.timer.stop()
        super().hideEvent(e)
    def load_cards(self, cards_data):
        self.timer.stop()
        for i in self.items: self.scene.removeItem(i)
        self.items.clear(); self.card_count=len(cards_data); self.progress=0.0; self.target_progress=0.0
        for i, data in enumerate(cards_data):
            item=DCCardItem(data,i); item.stripe_clicked.connect(self.card_clicked.emit)
            self.scene.addItem(item); self.items.append(item)
        # Start timer only if visible
        if self.isVisible() and self.card_count > 0:
            self.timer.start(16)
    def _on_tick(self):
        if not self.items:
            self.timer.stop()
            return
        self.progress+=(self.target_progress-self.progress)*DC_EASE
        cx=self.viewport().width()/2; cy=self.viewport().height()/2
        for item in self.items:
            off=item.index-self.progress; half=self.card_count/2
            while off>half: off-=self.card_count
            while off<-half: off+=self.card_count
            ao=abs(off); sign=1 if off>0 else(-1 if off<0 else 0)
            if ao>3.2: item.setVisible(False); continue
            item.setVisible(True)
            if ao<=1: t=_dc_smoothstep(ao); x=sign*t*(DC_CARD_W*0.62+DC_GAP); sc=1-t*0.30; op=1.0; z=100-t*40
            elif ao<=2: t=_dc_smoothstep(ao-1); x=sign*((DC_CARD_W*0.62+DC_GAP)+t*(DC_CARD_W*0.5)); sc=0.70-t*0.20; op=1.0-t*0.4; z=60-t*40
            else: t=_dc_smoothstep(min(ao-2,1)); x=sign*((DC_CARD_W*0.62+DC_GAP+DC_CARD_W*0.5)+t*(DC_CARD_W*0.6)); sc=max(0.2,0.50-t*0.3); op=max(0.0,0.6-t*0.6); z=20-t*20
            tr=QTransform(); tr.translate(cx+x,cy); tr.scale(sc*item.flipScale,sc)
            item.setTransform(tr); item.setZValue(z); item.setOpacity(op); item.update()
        self.viewport().update()
    def mousePressEvent(self, e):
        self._press_pos=e.pos(); self._press_item=self.itemAt(e.pos()); self._dragging=False; self._drag_start_progress=self.target_progress; super().mousePressEvent(e)
    def mouseMoveEvent(self, e):
        if e.buttons()&Qt.LeftButton and self._press_pos:
            dx=e.pos().x()-self._press_pos.x()
            if abs(dx)>DC_DRAG_TH: self._dragging=True
            if self._dragging: self.target_progress=self._drag_start_progress-dx/DC_PX_PER
        super().mouseMoveEvent(e)
    def mouseReleaseEvent(self, e):
        if self._dragging: self.target_progress=round(self.target_progress)
        else:
            item=self._press_item
            if isinstance(item,DCCardItem):
                lp=item.mapFromScene(self.mapToScene(e.pos()))
                if item.show_back and DC_STRIPE_RECT.contains(lp): self.card_clicked.emit(item.data.get("card_id",""))
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
# PREVIEW WIDGETS (independent)
# ═══════════════════════════════════════════════

class DCPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setFixedSize(DC_CARD_W, DC_CARD_H)
        self._data = {"card_name":"Card","card_network":"VISA","card_class":"","last_four":"0000","card_color_1":"#3a3a3a","card_color_2":"#0f0f0f"}
    def update_data(self, **kw): self._data.update(kw); self.update()
    def paintEvent(self, event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing); w,h=DC_CARD_W,DC_CARD_H; rect=QRectF(0,0,w,h)
        g=QLinearGradient(0,0,w,h); g.setColorAt(0,QColor(self._data.get("card_color_1","#3a3a3a"))); g.setColorAt(1,QColor(self._data.get("card_color_2","#0f0f0f")))
        p.setPen(Qt.NoPen); p.setBrush(g); p.drawRoundedRect(rect,DC_CARD_RADIUS,DC_CARD_RADIUS)
        p.setPen(QColor(255,255,255,235)); bf=QFont("Arial",13,QFont.Bold); bf.setLetterSpacing(QFont.AbsoluteSpacing,0.6); p.setFont(bf)
        p.drawText(QRectF(20,14,w-40,20),Qt.AlignLeft|Qt.AlignVCenter,self._data.get("card_name","Card"))
        brand=self._data.get("acct_name","")
        if brand: p.setPen(QColor(255,255,255,170)); p.setFont(QFont("Arial",10)); p.drawText(QRectF(20,34,w-40,16),Qt.AlignLeft|Qt.AlignVCenter,brand)
        chip=QRectF(24,h/2-13,34,26); cg=QLinearGradient(chip.topLeft(),chip.bottomLeft()); cg.setColorAt(0,QColor("#f2f2f2")); cg.setColorAt(1,QColor("#999999"))
        p.setPen(Qt.NoPen); p.setBrush(cg); p.drawRoundedRect(chip,4,4)
        network=self._data.get("card_network","VISA")
        if network and network != "OTHER":
            p.setPen(QColor(255,255,255,235)); tf=QFont("Arial",14,QFont.Bold); tf.setItalic(True); p.setFont(tf)
            p.drawText(QRectF(0,h-52,w-20,22),Qt.AlignRight|Qt.AlignVCenter,network)
        cls=self._data.get("card_class","")
        if cls: p.setPen(QColor(255,255,255,150)); p.setFont(QFont("Arial",10)); p.drawText(QRectF(0,h-32,w-20,18),Qt.AlignRight|Qt.AlignVCenter,cls)
        pen=QPen(QColor(255,255,255,40)); pen.setWidth(1); p.setPen(pen); p.setBrush(Qt.NoBrush); p.drawRoundedRect(rect.adjusted(0.5,0.5,-0.5,-0.5),DC_CARD_RADIUS,DC_CARD_RADIUS); p.end()

class DCBackPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setFixedSize(DC_CARD_W, DC_CARD_H)
        self._data = {"cardholder_name":"CARDHOLDER","last_four":"0000","expiry_month":12,"expiry_year":2028,"card_color_1":"#3a3a3a","card_color_2":"#0f0f0f"}
    def update_data(self, **kw): self._data.update(kw); self.update()
    def paintEvent(self, event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing); w,h=DC_CARD_W,DC_CARD_H; rect=QRectF(0,0,w,h)
        g=QLinearGradient(0,0,w,h); g.setColorAt(0,QColor(self._data.get("card_color_1","#3a3a3a"))); g.setColorAt(1,QColor(self._data.get("card_color_2","#0f0f0f")))
        p.setPen(Qt.NoPen); p.setBrush(g); p.drawRoundedRect(rect,DC_CARD_RADIUS,DC_CARD_RADIUS)
        p.setBrush(QColor(0,0,0,220)); p.drawRect(QRectF(0,20,w,32))
        p.setPen(QColor(255,255,255,150)); p.setFont(QFont("Arial",9,QFont.DemiBold)); p.drawText(QRectF(0,20,w,32),Qt.AlignCenter,"VIEW ACCOUNT DETAILS")
        p.setPen(QColor(255,255,255,200)); p.setFont(QFont("Arial",11)); p.drawText(QRectF(20,h-80,w-40,20),Qt.AlignLeft|Qt.AlignVCenter,self._data.get("cardholder_name","CARDHOLDER"))
        last4=self._data.get("last_four","0000")
        p.setPen(QColor(255,255,255,235)); p.setFont(QFont("Courier New",11,QFont.DemiBold)); p.drawText(QRectF(20,h-56,w-40,20),Qt.AlignLeft|Qt.AlignVCenter,f"XXXX  XXXX  XXXX  {last4}")
        em=self._data.get("expiry_month",12); ey=self._data.get("expiry_year",2028)
        p.setPen(QColor(255,255,255,170)); p.setFont(QFont("Courier New",9)); p.drawText(QRectF(20,h-34,w-40,20),Qt.AlignLeft|Qt.AlignVCenter,f"Valid: {em:02d}/{str(ey)[-2:]}")
        pen=QPen(QColor(255,255,255,40)); pen.setWidth(1); p.setPen(pen); p.setBrush(Qt.NoBrush); p.drawRoundedRect(rect.adjusted(0.5,0.5,-0.5,-0.5),DC_CARD_RADIUS,DC_CARD_RADIUS); p.end()


# ═══════════════════════════════════════════════
# ADD / EDIT DIALOG
# ═══════════════════════════════════════════════

class DebitCardAddDialog(QDialog):
    card_added = pyqtSignal()
    card_updated = pyqtSignal()

    def __init__(self, debit_cards_repo, accounts_repo, card=None, parent=None):
        super().__init__(parent)
        self.dcr = debit_cards_repo; self.acct = accounts_repo
        self._card = card; self._is_edit = card is not None
        self.setWindowTitle("\u270f\ufe0f  Edit Debit Card" if self._is_edit else "\U0001f4b3  Add Debit Card")
        self.setMinimumWidth(640); # Global QSS handles dialog background
        self._build()
        if self._is_edit: self._prefill()

    def _build(self):
        lay = QHBoxLayout(self); lay.setContentsMargins(24,24,24,24); lay.setSpacing(20)
        fc = QVBoxLayout(); fc.setSpacing(8)
        hdr = QLabel("\u270f\ufe0f  Edit Debit Card" if self._is_edit else "\U0001f4b3  Add Debit Card")
        hdr.setStyleSheet("font-size:18px;font-weight:800;color:#111827;"); fc.addWidget(hdr)
        form = QFormLayout(); form.setSpacing(8); form.setLabelAlignment(Qt.AlignRight)

        self.card_name = QLineEdit(); self.card_name.setPlaceholderText("e.g. SBI Debit Card"); self.card_name.textChanged.connect(self._upd); form.addRow("Card Name *", self.card_name)
        self.bank_combo = QComboBox(); self.bank_combo.setMinimumHeight(36); self._refresh_bank_combo(); self.bank_combo.currentIndexChanged.connect(self._upd); form.addRow("Bank (Current Acct) *", self.bank_combo)
        self.network = QComboBox(); self.network.addItems(["VISA","MASTERCARD","RUPAY","AMEX","OTHER"]); self.network.currentTextChanged.connect(self._upd); form.addRow("Network", self.network)
        self.card_class = QLineEdit(); self.card_class.setPlaceholderText("e.g. Classic, Platinum"); self.card_class.textChanged.connect(self._upd); form.addRow("Class", self.card_class)
        self.last_four = QLineEdit(); self.last_four.setMaxLength(4); self.last_four.setPlaceholderText("Last 4 digits"); self.last_four.textChanged.connect(self._upd); form.addRow("Last 4 Digits", self.last_four)
        self.cardholder = QLineEdit(); self.cardholder.setPlaceholderText("Name as on card"); self.cardholder.textChanged.connect(self._upd); form.addRow("Cardholder Name", self.cardholder)
        er = QHBoxLayout(); self.expiry_month = QSpinBox(); self.expiry_month.setRange(1,12); self.expiry_month.setValue(12)
        self.expiry_year = QSpinBox(); self.expiry_year.setRange(2024,2040); self.expiry_year.setValue(2028)
        self.expiry_month.valueChanged.connect(self._upd); self.expiry_year.valueChanged.connect(self._upd)
        er.addWidget(self.expiry_month); er.addWidget(QLabel("/")); er.addWidget(self.expiry_year); er.addStretch(); form.addRow("Expiry", er)
        self.annual_fee = QDoubleSpinBox(); self.annual_fee.setRange(0,99999); self.annual_fee.setPrefix("\u20b9 "); self.annual_fee.setDecimals(0); form.addRow("Annual Fee", self.annual_fee)
        self.color_idx = QComboBox()
        for name in DC_GRAD_NAMES: self.color_idx.addItem(name)
        self.color_idx.currentIndexChanged.connect(self._upd); form.addRow("Card Style", self.color_idx)
        fc.addLayout(form)
        br = QHBoxLayout(); br.addStretch(); c = QPushButton("Cancel"); c.clicked.connect(self.reject); br.addWidget(c)
        a = QPushButton("  Update  " if self._is_edit else "  Add Card  "); a.setObjectName("primary"); a.clicked.connect(self._save); br.addWidget(a); fc.addLayout(br); lay.addLayout(fc)

        pc = QVBoxLayout(); pc.setSpacing(8)
        fl = QLabel("Front"); fl.setStyleSheet(f"color:{C['text2']};font-size:13px;font-weight:700;"); pc.addWidget(fl)
        self.preview = DCPreviewWidget(); pc.addWidget(self.preview)
        bl = QLabel("Back"); bl.setStyleSheet(f"color:{C['text2']};font-size:13px;font-weight:700;"); pc.addWidget(bl)
        self.back_preview = DCBackPreviewWidget(); pc.addWidget(self.back_preview)
        self.toggle_btn = QPushButton(); self.toggle_btn.setMinimumHeight(36); self.toggle_btn.setCursor(QCursor(Qt.PointingHandCursor)); self.toggle_btn.clicked.connect(self._toggle_active)
        if self._is_edit: self._refresh_toggle_btn(); pc.addWidget(self.toggle_btn)
        else: self.toggle_btn.hide()
        pc.addStretch(); lay.addLayout(pc)

    def _refresh_bank_combo(self):
        self.bank_combo.clear()
        for a in self.acct.list_active():
            if a["account_type"] == "CURRENT": self.bank_combo.addItem(a["display_name"], a["account_id"])

    def _refresh_toggle_btn(self):
        if not self._is_edit or not self._card: return
        active = self._card.get("is_active", 1)
        if active:
            self.toggle_btn.setText("\u23f8  Deactivate Card")
            self.toggle_btn.setStyleSheet(f"QPushButton{{background:transparent;color:#DC2626;border:2px solid #DC2626;border-radius:8px;padding:6px 16px;font-size:12px;font-weight:700;}}QPushButton:hover{{background:#DC2626;color:white;}}")
        else:
            self.toggle_btn.setText("\u2705  Activate Card")
            self.toggle_btn.setStyleSheet(f"QPushButton{{background:transparent;color:#059669;border:2px solid #059669;border-radius:8px;padding:6px 16px;font-size:12px;font-weight:700;}}QPushButton:hover{{background:#059669;color:white;}}")

    def _toggle_active(self):
        if not self._is_edit or not self._card: return
        new_val = self.dcr.toggle_active(self._card["card_id"])
        QMessageBox.information(self, "Done", f"Card {'activated' if new_val else 'deactivated'}.")
        self.card_updated.emit(); self.accept()

    def _prefill(self):
        c = self._card; self.card_name.setText(c.get("card_name",""))
        aid = c.get("account_id","")
        for i in range(self.bank_combo.count()):
            if self.bank_combo.itemData(i) == aid: self.bank_combo.setCurrentIndex(i); break
        idx = self.network.findText(c.get("card_network","VISA"))
        if idx >= 0: self.network.setCurrentIndex(idx)
        self.card_class.setText(c.get("card_class","")); self.last_four.setText(c.get("last_four",""))
        self.cardholder.setText(c.get("cardholder_name","")); self.expiry_month.setValue(c.get("expiry_month",12))
        self.expiry_year.setValue(c.get("expiry_year",2028)); self.annual_fee.setValue(c.get("annual_fee",0))
        c1, c2 = c.get("card_color_1",""), c.get("card_color_2","")
        for i, (g1, g2) in enumerate(DC_GRADIENTS):
            if g1 == c1 and g2 == c2: self.color_idx.setCurrentIndex(i); break

    def _upd(self):
        c1, c2 = DC_GRADIENTS[self.color_idx.currentIndex()]
        d = dict(card_name=self.card_name.text().strip() or "Card", acct_name=self.bank_combo.currentText() or "",
                 card_network=self.network.currentText(), card_class=self.card_class.text().strip(),
                 cardholder_name=self.cardholder.text().strip() or "CARDHOLDER",
                 last_four=self.last_four.text().strip() or "0000",
                 expiry_month=self.expiry_month.value(), expiry_year=self.expiry_year.value(),
                 card_color_1=c1, card_color_2=c2)
        self.preview.update_data(**d); self.back_preview.update_data(**d)

    def _save(self):
        name = self.card_name.text().strip()
        if not name or self.bank_combo.currentIndex() < 0:
            QMessageBox.warning(self, "Missing", "Card name and bank account required."); return
        c1, c2 = DC_GRADIENTS[self.color_idx.currentIndex()]; account_id = self.bank_combo.currentData()
        if self._is_edit:
            self.dcr.update(self._card["card_id"], card_name=name, card_network=self.network.currentText(),
                card_class=self.card_class.text().strip(), last_four=self.last_four.text().strip() or "0000",
                cardholder_name=self.cardholder.text().strip() or name.upper(),
                expiry_month=self.expiry_month.value(), expiry_year=self.expiry_year.value(),
                annual_fee=self.annual_fee.value(), card_color_1=c1, card_color_2=c2, account_id=account_id)
            self.card_updated.emit()
        else:
            self.dcr.create(account_id=account_id, card_name=name, card_network=self.network.currentText(),
                card_class=self.card_class.text().strip(), last_four=self.last_four.text().strip() or "0000",
                cardholder_name=self.cardholder.text().strip() or name.upper(),
                expiry_month=self.expiry_month.value(), expiry_year=self.expiry_year.value(),
                annual_fee=self.annual_fee.value(), card_color_1=c1, card_color_2=c2)
            self.card_added.emit()
        self.accept()


# ═══════════════════════════════════════════════
# SMART LAZY SCROLL HELPERS
# ═══════════════════════════════════════════════

def _dc_month_groups(all_txns):
    by_month = OrderedDict()
    for tx in sorted(all_txns, key=lambda t: t.get("tx_date",""), reverse=True):
        mk = tx["tx_date"][:7]
        if mk not in by_month: by_month[mk] = {"txns":[], "debits":0.0, "credits":0.0}
        by_month[mk]["txns"].append(tx)
        if tx["tx_type"] == "DEBIT": by_month[mk]["debits"] += tx["amount"]
        else: by_month[mk]["credits"] += tx["amount"]
    result = []
    for mk, md in by_month.items():
        try: y, m = map(int, mk.split("-")); label = datetime(y,m,1).strftime("%B %Y")
        except: label = mk
        result.append({"key": mk, "label": label, **md})
    return result

def _dc_month_widgets(md, card=None):
    widgets = []
    net = md["credits"] - md["debits"]; nc = "#059669" if net >= 0 else "#DC2626"; nl = "Surplus" if net >= 0 else "Deficit"
    c1 = card.get("card_color_1","#3a3a3a") if card else "#3a3a3a"
    c2 = card.get("card_color_2","#0f0f0f") if card else "#0f0f0f"
    mh = QFrame(); mh.setMinimumHeight(52)
    mh.setStyleSheet(f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {c1}33,stop:1 {c2}33);border:1px solid {C['border2']};border-radius:10px;}}QLabel{{background:transparent;border:none;}}")
    ml = QHBoxLayout(mh); ml.setContentsMargins(16,8,16,8); ml.setSpacing(16)
    ml.addWidget(QLabel(f"<b style='font-size:15px;color:{C['text']};'>\U0001f4c5 {md['label']}</b>")); ml.addStretch()
    ml.addWidget(QLabel(f"<span style='font-size:13px;color:#DC2626;font-weight:700;'>Debits: {fmt_money(md['debits'])}</span>"))
    ml.addWidget(QLabel(f"<span style='font-size:13px;color:#059669;font-weight:700;'>Credits: {fmt_money(md['credits'])}</span>"))
    ml.addWidget(QLabel(f"<span style='font-size:13px;color:{nc};font-weight:800;'>{nl}: {fmt_money(abs(net))}</span>"))
    widgets.append(mh)
    by_date = OrderedDict()
    for tx in md["txns"]:
        d = tx["tx_date"]
        if d not in by_date: by_date[d] = []
        by_date[d].append(tx)
    for d_str, day_txns in by_date.items():
        try: day_label = date.fromisoformat(d_str).strftime("%A, %d %b")
        except: day_label = d_str
        widgets.append(_day_header(day_label))
        for tx in day_txns: widgets.append(_tx_card(tx))
    return widgets


# ═══════════════════════════════════════════════
# MAIN DEBIT CARDS TAB
# FIX 1: carousel wrapped in fixed_top (isolation layer)
# FIX 2: setFixedHeight on carousel
# FIX 4: setUpdatesEnabled during lazy scroll
# ═══════════════════════════════════════════════

class DebitCardsTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db; self.dcr = repos["debit_cards"]; self.acct = repos["accounts"]
        self.tx_repo = repos["transactions"]; self.bal = services["balance"]
        self._selected_card = None; self._pending_months = []; self._card_data = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(28,16,28,16); root.setSpacing(10)
        hr = QHBoxLayout(); hr.setSpacing(12)
        h = QLabel("\U0001f4b3  Debit Cards"); h.setStyleSheet("font-size:24px;font-weight:800;color:#111827;"); hr.addWidget(h); hr.addStretch()
        ab = QPushButton("\uff0b  Add Card"); ab.setObjectName("primary"); ab.setMinimumHeight(38)
        ab.setCursor(QCursor(Qt.PointingHandCursor)); ab.clicked.connect(self._add_card); hr.addWidget(ab); root.addLayout(hr)

        # ── fixed_top: tabs + carousel + header (pinned, isolation layer) ──
        fixed_top = QWidget()
        ft_lay = QVBoxLayout(fixed_top)
        ft_lay.setContentsMargins(4, 4, 4, 12)
        ft_lay.setSpacing(10)

        tabs_row = QHBoxLayout(); tabs_row.setSpacing(8)
        self.tab_active = QPushButton("\u2705  Active Cards"); self.tab_inactive = QPushButton("\u23f8  Closed Cards")
        self._sub_btns = [self.tab_active, self.tab_inactive]
        for b in self._sub_btns: b.setMinimumHeight(32); b.setCursor(QCursor(Qt.PointingHandCursor))
        self.tab_active.clicked.connect(lambda: self._switch_sub(0)); self.tab_inactive.clicked.connect(lambda: self._switch_sub(1))
        for b in self._sub_btns: tabs_row.addWidget(b)
        tabs_row.addStretch(); ft_lay.addLayout(tabs_row)

        self.carousel = DCCarouselView([])
        self.carousel.setFixedHeight(280)
        self.carousel.card_clicked.connect(self._on_card_clicked)
        ft_lay.addWidget(self.carousel)

        self.header_container = QWidget(); self.header_container.setStyleSheet("background:transparent;")
        self.header_lay = QVBoxLayout(self.header_container); self.header_lay.setContentsMargins(0,0,0,0); self.header_lay.setSpacing(0)
        self.header_container.hide()
        ft_lay.addWidget(self.header_container)

        left = QWidget()
        left_lay = QVBoxLayout(left); left_lay.setContentsMargins(0,0,0,0); left_lay.setSpacing(0)
        left_lay.addWidget(fixed_top)

        # ── details_scroll: persistent QScrollArea (never recreated) ──
        self.details_scroll = QScrollArea()
        self.details_scroll.setWidgetResizable(True)
        self.details_scroll.setFrameShape(QFrame.NoFrame)
        self.details_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self.details_container = QWidget()
        self.details_container.setStyleSheet("background:transparent;")
        self.details_container.hide()
        self.details_lay = QVBoxLayout(self.details_container)
        self.details_lay.setContentsMargins(0, 4, 0, 0)
        self.details_lay.setSpacing(12)
        self.details_scroll.setWidget(self.details_container)
        left_lay.addWidget(self.details_scroll, 1)

        root.addWidget(left, 1)
        self._switch_sub(0)

    def _switch_sub(self, idx):
        for i, b in enumerate(self._sub_btns): b.setStyleSheet(_dc_tab_active() if i == idx else _dc_tab_inactive())
        self._selected_card = None
        self.header_container.hide()
        # Clear transaction area immediately (prevents stale widgets from previous visit)
        while self.details_lay.count():
            itm = self.details_lay.takeAt(0)
            w = itm.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self.details_container.hide()
        self._load_cards()

    def _load_cards(self):
        # Auto-close expired cards
        today = date.today()
        for card in self.dcr.list_active():
            em = card.get("expiry_month", 12)
            ey = card.get("expiry_year", 2028)
            if ey < today.year or (ey == today.year and em < today.month):
                self.dcr.update(card["card_id"], is_active=0)

        active_idx = 0 if self._sub_btns[0].styleSheet() == _dc_tab_active() else 1
        cards = self.dcr.list_active() if active_idx == 0 else self.dcr.list_closed()
        self.carousel.load_cards(cards)

    def _on_card_clicked(self, card_id):
        card = self.dcr.get(card_id)
        if not card: return
        self._selected_card = card; self._show_details(card)

    def _show_details(self, card):
        # Clear details_lay immediately (same as CC tab _show_details)
        while self.details_lay.count():
            itm = self.details_lay.takeAt(0)
            w = itm.widget()
            if w:
                try:
                    sip.delete(w)
                except Exception:
                    w.deleteLater()

        # Clear header_container
        while self.header_lay.count():
            itm = self.header_lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()

        c1 = card.get("card_color_1","#3a3a3a"); c2 = card.get("card_color_2","#0f0f0f")

        # ── Header card (pinned in fixed_top) ──
        hdr = QFrame(); hdr.setFixedHeight(80)
        hdr.setStyleSheet(f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {c1},stop:1 {c2});border-radius:12px;}}QLabel{{background:transparent;}}")
        hdr_lay = QHBoxLayout(hdr); hdr_lay.setContentsMargins(20,12,20,12); hdr_lay.setSpacing(12)
        hdr_lay.addWidget(QLabel(f"<b style='font-size:16px;color:white;'>{card.get('card_name','Card')}</b>")); hdr_lay.addStretch()
        net_label = card.get("card_network","")
        if net_label == "OTHER": net_label = ""
        cls_label = card.get("card_class",""); sub_text = f"{net_label} {cls_label}".strip()
        if sub_text: hdr_lay.addWidget(QLabel(f"<span style='color:rgba(255,255,255,0.7);font-size:12px;'>{sub_text}</span>"))
        acct_name = card.get("acct_name","")
        if acct_name: hdr_lay.addWidget(QLabel(f"<span style='color:rgba(255,255,255,0.5);font-size:11px;'>\u2192 {acct_name}</span>"))
        edit_btn = QPushButton("\u270f\ufe0f  Edit Card")
        edit_btn.setStyleSheet("QPushButton{background:rgba(255,255,255,0.2);color:white;border:1px solid rgba(255,255,255,0.3);border-radius:6px;padding:4px 14px;font-size:11px;font-weight:700;}QPushButton:hover{background:rgba(255,255,255,0.35);}")
        edit_btn.setCursor(QCursor(Qt.PointingHandCursor)); edit_btn.setFixedHeight(28)
        edit_btn.clicked.connect(lambda: self._edit_card(card)); hdr_lay.addWidget(edit_btn)
        self.header_lay.addWidget(hdr)
        self.header_container.show()

        # ── Build transactions inside details_lay (same as CC tab) ──
        self._build_transactions_smart(card)
        self.details_container.show()

    def _build_transactions_smart(self, card):
        # Create FRESH inner scroll area (same as CC tab txn_scroll)
        txn_scroll = QScrollArea()
        txn_scroll.setWidgetResizable(True)
        txn_scroll.setFrameShape(QFrame.NoFrame)
        txn_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        txn_inner = QWidget()
        txn_inner.setStyleSheet("background:transparent;")
        txn_lay = QVBoxLayout(txn_inner)
        txn_lay.setSpacing(4)
        txn_lay.setContentsMargins(0, 0, 0, 0)
        self.tx_container_lay = txn_lay

        aid = card["account_id"]
        all_txns = self.tx_repo.list_filters(account_id=aid, limit=50000)

        if not all_txns:
            nt = QLabel("No transactions found for this account.")
            nt.setStyleSheet(f"color:{C['text3']};font-size:12px;padding:20px;")
            nt.setAlignment(Qt.AlignCenter)
            txn_lay.addWidget(nt)
            txn_lay.addStretch()
            txn_scroll.setWidget(txn_inner)
            self.details_lay.addWidget(txn_scroll, 1)
            return

        self._all_months = _dc_month_groups(all_txns)
        self._card_data = card
        self._loaded_months = 0

        # Smart initial: 1 month, expand if < 4 txns, up to 6
        months_to_load = 0
        total_txns = 0
        for i, md in enumerate(self._all_months):
            months_to_load = i + 1
            total_txns += len(md["txns"])
            if total_txns >= 4: break
            if months_to_load >= 6: break

        # Build all initial widgets BEFORE attaching to scroll
        txn_inner.setUpdatesEnabled(False)
        self._load_months_range(0, months_to_load)
        txn_lay.addStretch()
        txn_inner.setUpdatesEnabled(True)

        # Attach AFTER all widgets are added (like CC tab)
        txn_scroll.setWidget(txn_inner)
        self.details_lay.addWidget(txn_scroll, 1)

        # Lazy scroll for remaining months
        self._txn_scroll_ref = txn_scroll
        if self._loaded_months < len(self._all_months):
            txn_scroll.verticalScrollBar().valueChanged.connect(self._on_tx_scroll)

    def _load_months_range(self, start, end):
        for md in self._all_months[start:end]:
            for w in _dc_month_widgets(md, self._card_data): self.tx_container_lay.addWidget(w)
        self._loaded_months = end

    def _on_tx_scroll(self, value):
        sb = getattr(self, '_txn_scroll_ref', None)
        if not sb: return
        sb = sb.verticalScrollBar()
        if sb.maximum() <= 0: return
        if value >= sb.maximum() - 400: self._load_next_batch()

    def _load_next_batch(self):
        if self._loaded_months >= len(self._all_months): return
        end = self._loaded_months; total_txns = 0
        while end < len(self._all_months) and end - self._loaded_months < 3:
            total_txns += len(self._all_months[end]["txns"]); end += 1
            if total_txns >= 4: break
        # FIX 4: Disable updates during lazy scroll widget addition
        scroll = getattr(self, '_txn_scroll_ref', None)
        if scroll:
            scroll.widget().setUpdatesEnabled(False)
        self._load_months_range(self._loaded_months, end)
        if scroll:
            scroll.widget().setUpdatesEnabled(True)
        if self._loaded_months >= len(self._all_months):
            if scroll:
                try: scroll.verticalScrollBar().valueChanged.disconnect(self._on_tx_scroll)
                except: pass

    def _add_card(self):
        dlg = DebitCardAddDialog(self.dcr, self.acct, parent=self); dlg.card_added.connect(self.refresh); dlg.exec_()

    def _edit_card(self, card):
        dlg = DebitCardAddDialog(self.dcr, self.acct, card=card, parent=self); dlg.card_updated.connect(self.refresh); dlg.exec_()

    def refresh(self):
        self._selected_card = None
        self.header_container.hide()
        while self.details_lay.count():
            itm = self.details_lay.takeAt(0)
            w = itm.widget()
            if w:
                try: sip.delete(w)
                except: w.deleteLater()
        self.details_container.hide()
        self._load_cards()
