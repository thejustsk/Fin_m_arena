"""Cards Tab — Professional credit card management with FIFO payment allocation."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QFrame, QStackedWidget, QDialog,
                              QFormLayout, QLineEdit, QComboBox, QSpinBox,
                              QDoubleSpinBox, QMessageBox, QSizePolicy,
                              QGraphicsView, QGraphicsScene, QGraphicsObject,
                              QScrollArea, QSplitter, QDateEdit)
from PyQt5.QtCore import (Qt, QRectF, QPointF, QTimer, QPropertyAnimation,
                           QEasingCurve, pyqtProperty, pyqtSignal, QSize, QDate)
from PyQt5.QtGui import (QPainter, QColor, QLinearGradient, QFont,
                          QPainterPath, QPen, QTransform)
from datetime import date, datetime, timedelta
from collections import OrderedDict
from ui.theme import C
from ui.sidebar import fmt_money
from ui.tabs.database_tab import _tx_card, _day_header
import uuid

CARD_W = 320; CARD_H = 200; CARD_RADIUS = 16; GAP = 40
STRIPE_RECT = QRectF(-CARD_W / 2, -CARD_H / 2 + 20, CARD_W, 32)
EASE_FACTOR = 0.16; PX_PER_UNIT = CARD_W * 0.9; DRAG_THRESHOLD = 6

DEFAULT_GRADIENTS = [
    ("#3a3a3a", "#0f0f0f"),    # Meridian Bank
    ("#1c3d5a", "#0a0f14"),    # Solace Bank
    ("#4b2e2e", "#120909"),    # Vertex Trust
    ("#2e4b34", "#0a120c"),    # Palisade Bank
    ("#3a2e4b", "#0f0a14"),    # Anchorpoint Bank
    ("#4b3a1a", "#120d05"),    # Lumen Financial
    ("#1a3a3a", "#050f0f"),    # Cobalt Bank
    ("#4b1a3a", "#12050d"),    # Granite Trust
    ("#2a2a4b", "#08081b"),    # Auric Bank
    ("#4b3a2a", "#150f08"),    # Northgate Bank
    ("#1a2a4b", "#05081b"),    # Harborline Bank
    ("#3a1a1a", "#0f0505"),    # Sterling Vault
    ("#2a4b3a", "#081b10"),    # Cascade Bank
    ("#4a4a1a", "#141405"),    # Ridgeway Trust
    ("#1a4a3a", "#051410"),    # Ivory Bank
    ("#3a2a1a", "#0f0805"),    # Falcon Bank
    ("#2a1a3a", "#08051b"),    # Crescent Trust
    ("#4a1a2a", "#14050b"),    # Marble Bank
    ("#1a1a3a", "#05051b"),    # Obsidian Bank
    ("#3a4a1a", "#0f1405"),    # Summit Trust
]

GRADIENT_NAMES = [
    "Meridian Bank", "Solace Bank", "Vertex Trust", "Palisade Bank",
    "Anchorpoint Bank", "Lumen Financial", "Cobalt Bank", "Granite Trust",
    "Auric Bank", "Northgate Bank", "Harborline Bank", "Sterling Vault",
    "Cascade Bank", "Ridgeway Trust", "Ivory Bank", "Falcon Bank",
    "Crescent Trust", "Marble Bank", "Obsidian Bank", "Summit Trust",
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
# CYCLE & FIFO HELPERS
# ═══════════════════════════════════════════════

def _parse_stmt_day(stmt_str):
    try:
        day_str = "".join(c for c in stmt_str if c.isdigit())
        if day_str: return int(day_str)
    except: pass
    return None


def _calc_due(stmt_str, grace_days):
    day = _parse_stmt_day(stmt_str)
    if not day: return ""
    today = date.today()
    stmt = today.replace(day=min(day, 28))
    if stmt <= today:
        if today.month == 12: stmt = stmt.replace(year=today.year + 1, month=1)
        else: stmt = stmt.replace(month=today.month + 1)
    return (stmt + timedelta(days=grace_days)).isoformat()


def _ordinal(n):
    """Return n with ordinal suffix: 1st, 2nd, 3rd, 20th, etc."""
    if 11 <= (n % 100) <= 13: return f"{n}th"
    return f"{n}{['th','st','nd','rd','th','th','th','th','th','th'][n % 10]}"


def _stmt_display(stmt_str):
    """Format statement date with ordinal: '6th', '20th', etc."""
    if not stmt_str: return "—"
    day = _parse_stmt_day(stmt_str)
    if day: return _ordinal(day)
    return stmt_str


def _cycle_name(start_date):
    """Cycle name = start month + year, e.g. 'Jan 2025'."""
    return start_date.strftime("%b %Y")


def _build_cycles(stmt_day, num=8):
    """Build cycles from statement day. Includes current period.
    Returns list of (start, end) tuples, newest first.
    """
    if not stmt_day:
        return []
    today = date.today()
    sd = min(stmt_day, 28)

    # Find most recent statement date <= today
    cur = today.replace(day=sd)
    if cur > today:
        cur = (cur.replace(day=1) - timedelta(days=1)).replace(day=sd)

    # Generate statement dates going backwards
    stmt_dates = [cur]
    for _ in range(num - 1):
        prev = (cur.replace(day=1) - timedelta(days=1))
        cur = prev.replace(day=sd)
        stmt_dates.append(cur)
    stmt_dates.reverse()  # oldest first

    # Add NEXT statement date to cover current period
    last = stmt_dates[-1]
    if last.month == 12:
        nxt = last.replace(year=last.year + 1, month=1, day=sd)
    else:
        nxt = last.replace(month=last.month + 1, day=sd)
    stmt_dates.append(nxt)

    # Build cycles
    cycles = []
    for i in range(1, len(stmt_dates)):
        cycles.append((stmt_dates[i - 1] + timedelta(days=1), stmt_dates[i]))
    cycles.reverse()  # newest first
    return cycles


def _fifo_allocate(cycles, all_txns):
    """FIFO payment allocation across cycles.
    Returns list of dicts: {start, end, debits, paid, remaining, txns}
    """
    # Build cycle data with transactions
    cycle_data = []
    for cs, ce in cycles:
        cs_str = cs.isoformat(); ce_str = ce.isoformat()
        cx = [t for t in all_txns if cs_str <= t["tx_date"] <= ce_str]
        debits = sum(t["amount"] for t in cx if t["tx_type"] == "DEBIT")
        cycle_data.append({
            "start": cs, "end": ce,
            "debits": debits, "paid": 0, "remaining": debits,
            "txns": cx
        })

    # Get all credit transactions (payments) sorted by date
    credits = sorted(
        [t for t in all_txns if t["tx_type"] == "CREDIT"],
        key=lambda t: t["tx_date"]
    )

    # FIFO: allocate each payment to oldest cycle with remaining > 0
    for tx in credits:
        amt = tx["amount"]
        for cd in reversed(cycle_data):  # oldest first
            if cd["remaining"] > 0 and amt > 0:
                alloc = min(amt, cd["remaining"])
                cd["paid"] += alloc
                cd["remaining"] -= alloc
                amt -= alloc
            if amt <= 0:
                break

    return cycle_data


# ═══════════════════════════════════════════════
# CARD ITEM (carousel)
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
        network=self.data.get("card_network","VISA")
        if network and network != "OTHER":
            painter.setPen(QColor(255,255,255,235)); tf=QFont("Arial",14,QFont.Bold); tf.setItalic(True); tf.setLetterSpacing(QFont.AbsoluteSpacing,1.0); painter.setFont(tf)
            painter.drawText(QRectF(-w/2,h/2-52,w-20,22), Qt.AlignRight|Qt.AlignVCenter, network)
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
# PREVIEW WIDGETS
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
        network=self._data.get("card_network","VISA")
        if network and network != "OTHER":
            p.setPen(QColor(255,255,255,235)); tf=QFont("Arial",14,QFont.Bold); tf.setItalic(True); p.setFont(tf)
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
    card_updated = pyqtSignal()
    def __init__(self, cards_repo, accounts_repo, card=None, parent=None):
        super().__init__(parent); self.cr=cards_repo; self.acct=accounts_repo
        self._card = card; self._is_edit = card is not None
        title = "✏️  Edit Credit Card" if self._is_edit else "💳  Add New Credit Card"
        self.setWindowTitle(title); self.setMinimumWidth(640)
        self.setStyleSheet(f"QDialog{{background:{C['bg']};}}"); self._build()
        if self._is_edit: self._prefill()
    def _build(self):
        lay=QHBoxLayout(self); lay.setContentsMargins(24,24,24,24); lay.setSpacing(20)
        fc=QVBoxLayout(); fc.setSpacing(8)
        hdr_text = "✏️  Edit Credit Card" if self._is_edit else "💳  Add New Credit Card"
        hdr=QLabel(hdr_text); hdr.setStyleSheet("font-size:18px;font-weight:800;color:#111827;"); fc.addWidget(hdr)
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
        self.statement_date=QLineEdit(); self.statement_date.setPlaceholderText("e.g. 6th"); form.addRow("Statement Date",self.statement_date)
        self.grace_days=QSpinBox(); self.grace_days.setRange(0,55); self.grace_days.setValue(20); form.addRow("Grace Period (days)",self.grace_days)
        self.annual_fee=QDoubleSpinBox(); self.annual_fee.setRange(0,99999); self.annual_fee.setPrefix("₹ "); self.annual_fee.setDecimals(0); form.addRow("Annual Fee",self.annual_fee)
        self.color_idx=QComboBox()
        for name in GRADIENT_NAMES: self.color_idx.addItem(name)
        self.color_idx.currentIndexChanged.connect(self._upd); form.addRow("Card Style",self.color_idx)
        fc.addLayout(form)
        br=QHBoxLayout(); br.addStretch(); c=QPushButton("Cancel"); c.clicked.connect(self.reject); br.addWidget(c)
        btn_text = "  Update  " if self._is_edit else "  Add Card  "
        a=QPushButton(btn_text); a.setObjectName("primary"); a.clicked.connect(self._save); br.addWidget(a); fc.addLayout(br); lay.addLayout(fc)
        pc=QVBoxLayout(); pc.setSpacing(8)
        fl=QLabel("Front"); fl.setStyleSheet(f"color:{C['text2']};font-size:13px;font-weight:700;"); pc.addWidget(fl)
        self.preview=CardPreviewWidget(); pc.addWidget(self.preview)
        bl=QLabel("Back"); bl.setStyleSheet(f"color:{C['text2']};font-size:13px;font-weight:700;"); pc.addWidget(bl)
        self.back_preview=CardBackPreviewWidget(); pc.addWidget(self.back_preview)
        # Activate / Deactivate button (always visible, works in both add & edit)
        self.toggle_btn = QPushButton()
        self.toggle_btn.setMinimumHeight(36); self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle_active)
        if self._is_edit:
            self._refresh_toggle_btn()
            pc.addWidget(self.toggle_btn)
        else:
            self.toggle_btn.hide()
        pc.addStretch(); lay.addLayout(pc)
    def _refresh_toggle_btn(self):
        if not self._is_edit or not self._card: return
        active = self._card.get("is_active", 1)
        if active:
            self.toggle_btn.setText("⏸  Deactivate Card")
            self.toggle_btn.setStyleSheet(f"QPushButton{{background:transparent;color:#DC2626;border:2px solid #DC2626;border-radius:8px;padding:6px 16px;font-size:12px;font-weight:700;}}QPushButton:hover{{background:#DC2626;color:white;}}")
        else:
            self.toggle_btn.setText("✅  Activate Card")
            self.toggle_btn.setStyleSheet(f"QPushButton{{background:transparent;color:#059669;border:2px solid #059669;border-radius:8px;padding:6px 16px;font-size:12px;font-weight:700;}}QPushButton:hover{{background:#059669;color:white;}}")
    def _toggle_active(self):
        if not self._is_edit or not self._card: return
        cid = self._card["card_id"]
        aid = self._card["account_id"]
        cur = self._card.get("is_active", 1)
        new_val = 0 if cur else 1
        # Update BOTH card and account — no silent errors
        self.cr.update(cid, is_active=new_val)
        self.acct.update(aid, is_active=new_val)
        # Sync ALL cards under this account
        self.cr.db.execute("UPDATE cards SET is_active=? WHERE account_id=?", (new_val, aid))
        self.cr.db.commit()
        state = "activated" if new_val else "deactivated"
        QMessageBox.information(self, "Done", f"Card {state}.")
        self.card_updated.emit(); self.accept()
    def _prefill(self):
        c = self._card
        self.card_name.setText(c.get("card_name",""))
        self.issuer.setText(c.get("issuer_bank",""))
        self.brand.setText(c.get("card_brand",""))
        net = c.get("card_network","VISA")
        idx = self.network.findText(net)
        if idx >= 0: self.network.setCurrentIndex(idx)
        self.card_class.setText(c.get("card_class",""))
        self.last_four.setText(c.get("last_four",""))
        self.cardholder.setText(c.get("cardholder_name",""))
        lim = c.get("credit_limit",0) or c.get("acct_limit",0)
        self.credit_limit.setValue(lim)
        self.expiry_month.setValue(c.get("expiry_month",12))
        self.expiry_year.setValue(c.get("expiry_year",2028))
        self.statement_date.setText(c.get("statement_date",""))
        self.grace_days.setValue(c.get("grace_days",20))
        self.annual_fee.setValue(c.get("annual_fee",0))
        # Find gradient index by matching colors
        c1 = c.get("card_color_1",""); c2 = c.get("card_color_2","")
        for i, (g1, g2) in enumerate(DEFAULT_GRADIENTS):
            if g1 == c1 and g2 == c2:
                self.color_idx.setCurrentIndex(i); break
    def _upd(self):
        c1,c2=DEFAULT_GRADIENTS[self.color_idx.currentIndex()]
        d=dict(issuer_bank=self.issuer.text().strip() or "BANK",card_brand=self.brand.text().strip(),card_network=self.network.currentText(),card_class=self.card_class.text().strip(),cardholder_name=self.cardholder.text().strip() or "CARDHOLDER",last_four=self.last_four.text().strip() or "0000",expiry_month=self.expiry_month.value(),expiry_year=self.expiry_year.value(),card_color_1=c1,card_color_2=c2)
        self.preview.update_data(**d); self.back_preview.update_data(**d)
    def _save(self):
        name=self.card_name.text().strip(); bank=self.issuer.text().strip(); limit=self.credit_limit.value()
        if not name or not bank or limit<=0: QMessageBox.warning(self,"Missing","Card name, bank, and credit limit required."); return
        c1,c2=DEFAULT_GRADIENTS[self.color_idx.currentIndex()]
        if self._is_edit:
            # ── UPDATE mode ──
            cid = self._card["card_id"]; aid = self._card["account_id"]
            due = _calc_due(self.statement_date.text().strip(), self.grace_days.value())
            self.cr.update(cid,
                card_name=name, issuer_bank=bank,
                card_brand=self.brand.text().strip(),
                card_network=self.network.currentText(),
                card_class=self.card_class.text().strip(),
                last_four=self.last_four.text().strip() or "0000",
                cardholder_name=self.cardholder.text().strip() or name.upper(),
                expiry_month=self.expiry_month.value(),
                expiry_year=self.expiry_year.value(),
                statement_date=self.statement_date.text().strip(),
                due_date=due, grace_days=self.grace_days.value(),
                annual_fee=self.annual_fee.value(),
                card_color_1=c1, card_color_2=c2)
            # Sync account display name
            try: self.acct.update(aid, display_name=name, short_label=name[:8].upper(), credit_limit=limit)
            except: pass
            self.card_updated.emit(); self.accept()
        else:
            # ── CREATE mode ──
            existing=None
            for a in self.acct.list_active():
                if a["display_name"].upper()==name.upper(): existing=a; break
            if existing: aid=existing["account_id"]
            else:
                aid=str(uuid.uuid4())
                self.acct.create(account_id=aid,display_name=name,short_label=name[:8].upper(),account_type="CREDIT_CARD",credit_limit=limit,opening_balance=0,color_hex="#7C3AED")
            due = _calc_due(self.statement_date.text().strip(), self.grace_days.value())
            self.cr.create(account_id=aid,card_name=name,issuer_bank=bank,card_brand=self.brand.text().strip(),card_network=self.network.currentText(),card_class=self.card_class.text().strip(),last_four=self.last_four.text().strip() or "0000",cardholder_name=self.cardholder.text().strip() or name.upper(),expiry_month=self.expiry_month.value(),expiry_year=self.expiry_year.value(),statement_date=self.statement_date.text().strip(),due_date=due,grace_days=self.grace_days.value(),annual_fee=self.annual_fee.value(),card_color_1=c1,card_color_2=c2)
            self.card_added.emit(); self.accept()


# ═══════════════════════════════════════════════
# REMINDERS WIDGET (FIFO-based)
# ═══════════════════════════════════════════════

class RemindersWidget(QWidget):
    def __init__(self, cards_repo, tx_repo=None, bal_svc=None, parent=None):
        super().__init__(parent); self.cr=cards_repo; self.tx_repo=tx_repo; self.bal=bal_svc
        self.setStyleSheet("background:transparent;")
        self.lay=QVBoxLayout(self); self.lay.setContentsMargins(0,0,0,0); self.lay.setSpacing(6)

    def load_reminders(self, cards):
        while self.lay.count():
            itm=self.lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()

        title = QLabel("⏰  Reminders")
        title.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:700;")
        self.lay.addWidget(title)
        today = date.today()
        reminders = []

        for card in cards:
            name = card.get("card_name", card.get("issuer_bank", "Card"))
            aid = card["account_id"]
            stmt_str = card.get("statement_date", "")
            grace = card.get("grace_days", 20)
            stmt_day = _parse_stmt_day(stmt_str)

            if not stmt_day:
                continue

            # Outstanding balance for statement-reminder check
            outstanding = 0
            if self.bal:
                try: outstanding = abs(self.bal.get_balance(aid))
                except: pass

            # Type 1: Statement generating (5 days before statement, only if balance > 0)
            if stmt_day:
                try:
                    stmt = today.replace(day=min(stmt_day, 28))
                    if stmt <= today:
                        if today.month == 12:
                            stmt = stmt.replace(year=today.year + 1, month=1)
                        else:
                            stmt = stmt.replace(month=today.month + 1)
                    du = (stmt - today).days
                    if 0 <= du <= 5 and outstanding > 0:
                        col = "#D97706" if du <= 2 else "#4F46E5"
                        reminders.append((du, f"📅 {name} — Statement in {du}d (₹{outstanding:,.0f})", col))
                except:
                    pass

            # ── Due reminders — per-cycle from card_cycles table ──
            # Current cycle = statement_date >= today → skip
            # Previous cycles = statement_date < today AND remaining > 0 → generate reminder
            try:
                saved_cycles = self.cr.get_cycles(aid)
            except:
                saved_cycles = []
            today_iso = today.isoformat()
            for cyc in saved_cycles:
                # cyc fields: cycle_start_date, statement_date (=cycle end), remaining, due_date
                cyc_end = cyc.get("statement_date", "")
                if not cyc_end or cyc_end >= today_iso:
                    continue  # current cycle — skip

                remaining = cyc.get("remaining", 0) or 0
                if remaining <= 0:
                    continue  # fully paid — skip

                due_date_str = cyc.get("due_date", "") or ""
                if not due_date_str or "-" not in due_date_str:
                    continue  # no due date set — skip

                # Build cycle name from cycle_start_date
                cs_str = cyc.get("cycle_start_date", "")
                try:
                    cycle_nm = _cycle_name(date.fromisoformat(cs_str))
                except:
                    cycle_nm = cs_str

                try:
                    due_dt = date.fromisoformat(due_date_str)
                    dd = (due_dt - today).days
                except:
                    continue

                if dd < 0:
                    # OVERDUE — due date has passed
                    reminders.append((-100, f"🚨 OVERDUE {abs(dd)}d — {name} ({cycle_nm})  ₹{remaining:,.0f}", "#DC2626"))
                else:
                    # UPCOMING due
                    col = "#D97706" if dd <= 3 else "#059669"
                    reminders.append((dd, f"💰 Due in {dd}d — {name} ({cycle_nm})  ₹{remaining:,.0f}", col))

        # High-value transactions
        min_limit = 499
        try:
            for pref in self.cr.db.execute("SELECT value FROM preferences WHERE key='min_txn_alert'").fetchall():
                min_limit = int(pref[0])
        except: pass
        if self.tx_repo:
            five_days_ago = (today - timedelta(days=5)).isoformat()
            for card in cards:
                name = card.get("card_name", card.get("issuer_bank", "Card"))
                try:
                    txns = self.tx_repo.list_filters(account_id=card["account_id"], date_from=five_days_ago, date_to=today.isoformat(), limit=50)
                    for tx in txns:
                        if tx["amount"] >= min_limit and tx["tx_type"] == "DEBIT":
                            # Format date as DD/MM
                            try:
                                d = date.fromisoformat(tx["tx_date"])
                                date_str = d.strftime("%d/%m")
                            except:
                                date_str = tx["tx_date"][5:] if len(tx["tx_date"]) > 5 else tx["tx_date"]
                            reminders.append((3, f"⚡ {name} — ₹{tx['amount']:,.0f} on {date_str}", "#8B5CF6"))
                except: pass

        reminders.sort(key=lambda r: r[0])
        if not reminders:
            lbl = QLabel("No upcoming reminders.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;")
            self.lay.addWidget(lbl)
        else:
            for _, text, color in reminders[:15]:
                row = QFrame()
                row.setStyleSheet(f"background:{C['surface']};border:1px solid {C['border2']};border-radius:8px;padding:6px 10px;")
                rl = QHBoxLayout(row); rl.setContentsMargins(8, 4, 8, 4)
                dot = QLabel("■"); dot.setFixedWidth(16); dot.setFixedHeight(16)
                dot.setStyleSheet(f"background:{color};border-radius:3px;")
                rl.addWidget(dot)
                lbl = QLabel(text)
                lbl.setStyleSheet(f"color:{C['text']};font-size:11px;")
                lbl.setWordWrap(True)
                rl.addWidget(lbl, 1)
                self.lay.addWidget(row)
        self.lay.addStretch()


# ═══════════════════════════════════════════════
# MAIN CARDS TAB
# ═══════════════════════════════════════════════

class CardsTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db; self.cr = repos["cards"]; self.acct = repos["accounts"]
        self.tx_repo = repos["transactions"]; self.bal = services["balance"]
        self._selected_card = None; self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(28, 16, 28, 16); root.setSpacing(10)
        hr = QHBoxLayout(); hr.setSpacing(12)
        h = QLabel("💳  Credit Cards"); h.setStyleSheet("font-size:24px;font-weight:800;color:#111827;"); hr.addWidget(h); hr.addStretch()
        ab = QPushButton("＋  Add Card"); ab.setObjectName("primary"); ab.setMinimumHeight(38)
        ab.setCursor(Qt.PointingHandCursor); ab.clicked.connect(self._add_card); hr.addWidget(ab)
        root.addLayout(hr)

        splitter = QSplitter(Qt.Horizontal); splitter.setStyleSheet("QSplitter{background:transparent;border:none;}")

        left = QWidget(); left_lay = QVBoxLayout(left); left_lay.setContentsMargins(0, 0, 0, 0); left_lay.setSpacing(0)
        fixed_top = QWidget(); ft_lay = QVBoxLayout(fixed_top); ft_lay.setContentsMargins(4, 4, 4, 12); ft_lay.setSpacing(10)

        tabs_row = QHBoxLayout(); tabs_row.setSpacing(8)
        self.tab_active = QPushButton("✅  Active Cards"); self.tab_inactive = QPushButton("⏸  Closed Cards")
        self._sub_btns = [self.tab_active, self.tab_inactive]
        for b in self._sub_btns: b.setMinimumHeight(32); b.setCursor(Qt.PointingHandCursor)
        self.tab_active.clicked.connect(lambda: self._switch_sub(0)); self.tab_inactive.clicked.connect(lambda: self._switch_sub(1))
        for b in self._sub_btns: tabs_row.addWidget(b)
        tabs_row.addStretch(); ft_lay.addLayout(tabs_row)

        self.carousel = CarouselView([]); self.carousel.setMinimumHeight(260); self.carousel.setMaximumHeight(320)
        self.carousel.card_clicked.connect(self._on_card_clicked); ft_lay.addWidget(self.carousel)

        self.header_container = QWidget(); self.header_container.setStyleSheet("background:transparent;")
        self.header_lay = QVBoxLayout(self.header_container)
        self.header_lay.setContentsMargins(0, 0, 0, 0); self.header_lay.setSpacing(0)
        self.header_container.hide()
        ft_lay.addWidget(self.header_container)
        left_lay.addWidget(fixed_top)

        self.details_scroll = QScrollArea(); self.details_scroll.setWidgetResizable(True)
        self.details_scroll.setFrameShape(QFrame.NoFrame); self.details_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self.details_container = QWidget(); self.details_container.setStyleSheet("background:transparent;"); self.details_container.hide()
        self.details_lay = QVBoxLayout(self.details_container); self.details_lay.setContentsMargins(0, 4, 0, 0); self.details_lay.setSpacing(12)
        self.details_scroll.setWidget(self.details_container)
        left_lay.addWidget(self.details_scroll, 1)

        # Settlement footer
        self.settle_footer = QFrame()
        self.settle_footer.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:10px;padding:10px 14px;}}")
        self.settle_footer.hide()
        sf_lay = QHBoxLayout(self.settle_footer); sf_lay.setContentsMargins(10, 6, 10, 6); sf_lay.setSpacing(12)
        sf_lay.addWidget(QLabel("<b>Repay:</b>"))
        self.sf_opt = QComboBox(); self.sf_opt.setMinimumHeight(32); self.sf_opt.setMaximumWidth(250)
        self.sf_opt.currentIndexChanged.connect(self._on_sf_opt_changed); sf_lay.addWidget(self.sf_opt)
        self.sf_custom_row = QWidget()
        custom_lay = QHBoxLayout(self.sf_custom_row); custom_lay.setContentsMargins(0, 0, 0, 0); custom_lay.setSpacing(6)
        custom_lay.addWidget(QLabel("₹"))
        self.sf_custom_amt = QDoubleSpinBox(); self.sf_custom_amt.setRange(0, 99999999); self.sf_custom_amt.setDecimals(0)
        self.sf_custom_amt.setMinimumHeight(32); self.sf_custom_amt.setMaximumWidth(120); custom_lay.addWidget(self.sf_custom_amt)
        self.sf_custom_row.hide(); sf_lay.addWidget(self.sf_custom_row)
        sf_lay.addWidget(QLabel("From:"))
        self.sf_src = QComboBox(); self.sf_src.setMinimumHeight(32); self.sf_src.setMaximumWidth(180); sf_lay.addWidget(self.sf_src)
        sf_lay.addWidget(QLabel("Method:"))
        self.sf_method = QComboBox(); self.sf_method.addItems(PAYMENT_METHODS); self.sf_method.setMinimumHeight(32); self.sf_method.setMaximumWidth(140); sf_lay.addWidget(self.sf_method)
        sf_lay.addWidget(QLabel("Date:"))
        self.sf_date = QDateEdit(); self.sf_date.setDate(QDate.currentDate())
        self.sf_date.setCalendarPopup(True); self.sf_date.setDisplayFormat("dd MMM yyyy")
        self.sf_date.setMinimumHeight(32); self.sf_date.setMaximumWidth(130)
        sf_lay.addWidget(self.sf_date)
        sf_lay.addStretch()
        self.sf_btn = QPushButton("💰  Settle")
        self.sf_btn.setStyleSheet(f"QPushButton{{background:transparent;color:{C['accent']};border:2px solid {C['accent']};border-radius:8px;padding:6px 20px;font-size:13px;font-weight:700;}}QPushButton:hover{{background:{C['accent']};color:white;}}")
        self.sf_btn.setMinimumHeight(34); self.sf_btn.setCursor(Qt.PointingHandCursor)
        self.sf_btn.clicked.connect(self._settle_from_footer); sf_lay.addWidget(self.sf_btn)
        left_lay.addWidget(self.settle_footer)
        splitter.addWidget(left)

        # RIGHT PANEL — Reminders
        right = QWidget(); right.setMinimumWidth(280)
        right_lay = QVBoxLayout(right); right_lay.setContentsMargins(8, 0, 0, 0); right_lay.setSpacing(0)
        self.reminders = RemindersWidget(self.cr, self.tx_repo, self.bal)
        rem_scroll = QScrollArea(); rem_scroll.setWidgetResizable(True); rem_scroll.setFrameShape(QFrame.NoFrame)
        rem_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}"); rem_scroll.setWidget(self.reminders)
        right_lay.addWidget(rem_scroll)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3); splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)
        self._switch_sub(0)

    def _switch_sub(self, idx):
        for i, b in enumerate(self._sub_btns): b.setStyleSheet(_tab_btn_active() if i == idx else _tab_btn_inactive())
        self._selected_card = None; self.details_container.hide(); self.header_container.hide(); self.settle_footer.hide()
        self._load_cards()

    def _utils(self, cards):
        u = {}
        for card in cards:
            aid = card["account_id"]; lim = card.get("credit_limit", 0) or card.get("acct_limit", 0)
            u[aid] = min(abs(self.bal.get_balance(aid)) / lim, 1.0) if lim > 0 else 0.0
        return u

    def _load_cards(self):
        ac = self.cr.list_active()
        ic = [dict(r) for r in self.db.execute(
            "SELECT c.*,a.display_name AS acct_name,a.credit_limit AS acct_limit "
            "FROM cards c JOIN accounts a ON a.account_id=c.account_id "
            "WHERE c.is_active=0 ORDER BY c.sort_order").fetchall()]
        active_idx = 0 if self._sub_btns[0].styleSheet() == _tab_btn_active() else 1
        cards = ac if active_idx == 0 else ic
        # Save cycles for all active cards (needed for reminders + sidebar)
        for card in ac:
            self._save_cycles(card)
        self.carousel.load_cards(cards, self._utils(cards))
        self.reminders.load_reminders(ac)

    def _save_cycles(self, card):
        """Compute FIFO and save cycle data to card_cycles table."""
        aid = card["account_id"]
        stmt_day = _parse_stmt_day(card.get("statement_date", ""))
        grace = card.get("grace_days", 20)
        if not stmt_day:
            return
        all_txns = self.tx_repo.list_filters(account_id=aid, limit=50000)
        # Build enough cycles to cover ALL transactions
        if all_txns:
            oldest_tx = min(t["tx_date"] for t in all_txns)
            oldest_dt = date.fromisoformat(oldest_tx)
            months_back = (date.today().year - oldest_dt.year) * 12 + (date.today().month - oldest_dt.month) + 2
            num_cycles = max(12, months_back)
            cycles = _build_cycles(stmt_day, num_cycles)
        else:
            cycles = _build_cycles(stmt_day, 12)
        cycle_data = _fifo_allocate(cycles, all_txns)
        # Preserve existing due_dates from DB
        existing = {c["cycle_start_date"]: c for c in self.cr.get_cycles(aid)}
        for cd in cycle_data:
            cs_str = cd["start"].isoformat()
            ce_str = cd["end"].isoformat()
            # Use existing due_date if edited, otherwise calculate default
            existing_due = existing.get(cs_str, {}).get("due_date", "")
            if not existing_due:
                try: existing_due = (cd["end"] + timedelta(days=grace)).isoformat()
                except: existing_due = ""
            self.cr.upsert_cycle(
                account_id=aid,
                cycle_start_date=cs_str,
                statement_date=ce_str,
                debits=cd["debits"],
                paid=cd["paid"],
                remaining=cd["remaining"],
                due_date=existing_due,
                total_due=cd["remaining"],
                minimum_due=round(cd["remaining"] * 0.05, 2) if cd["remaining"] > 0 else 0,
            )
        # Force commit to ensure data is visible
        try: self.db.get().commit()
        except: pass

    def _on_card_clicked(self, card_id):
        card = self.cr.get(card_id)
        if not card: return
        self._selected_card = card; self._show_details(card)

    def _show_details(self, card):
        # Clear
        while self.header_lay.count():
            itm = self.header_lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()
        while self.details_lay.count():
            itm = self.details_lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()

        aid = card["account_id"]
        limit = card.get("credit_limit", 0) or card.get("acct_limit", 0)
        balance = abs(self.bal.get_balance(aid))
        util = (balance / limit * 100) if limit > 0 else 0
        c1 = card.get("card_color_1", "#3a3a3a"); c2 = card.get("card_color_2", "#0f0f0f")
        stmt_date = card.get("statement_date", "—") or "—"
        util_color = "#EF4444" if util > 70 else ("#F59E0B" if util > 30 else "#10B981")

        due_str = card.get("due_date", "") or ""
        if not due_str:
            due_str = _calc_due(card.get("statement_date", ""), card.get("grace_days", 20))

        # ── Header: Two-balance display + editable due date ──
        hdr = QFrame(); hdr.setFixedHeight(110)
        hdr.setStyleSheet(f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {c1},stop:1 {c2});border-radius:12px;}}QLabel{{background:transparent;}}")
        hdr_lay = QVBoxLayout(hdr); hdr_lay.setContentsMargins(20, 12, 20, 12); hdr_lay.setSpacing(6)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel(f"<b style='font-size:16px;color:white;'>{card.get('card_name', 'Card')}</b>"))
        r1.addStretch()
        net_label = card.get('card_network', '')
        if net_label == "OTHER": net_label = ''
        cls_label = card.get('card_class', '')
        sub_text = f"{net_label} {cls_label}".strip()
        if sub_text:
            r1.addWidget(QLabel(f"<span style='color:rgba(255,255,255,0.7);font-size:12px;'>{sub_text}</span>"))
        hdr_lay.addLayout(r1)

        # Two-balance: Statement Balance + Current Balance
        r2 = QHBoxLayout(); r2.setSpacing(24)
        # Load transactions
        self._current_all_txns = self.tx_repo.list_filters(account_id=aid, limit=50000)
        stmt_day = _parse_stmt_day(card.get("statement_date", ""))
        # Build enough cycles to cover ALL transactions
        if stmt_day and self._current_all_txns:
            oldest_tx = min(t["tx_date"] for t in self._current_all_txns)
            oldest_dt = date.fromisoformat(oldest_tx)
            months_back = (date.today().year - oldest_dt.year) * 12 + (date.today().month - oldest_dt.month) + 2
            num_cycles = max(12, months_back)
            all_cycles = _build_cycles(stmt_day, num_cycles)
        else:
            all_cycles = _build_cycles(stmt_day, 12) if stmt_day else []

        # Load saved cycles from DB
        try:
            saved_cycles = self.cr.get_cycles(aid)
        except:
            saved_cycles = []
        saved_map = {c["cycle_start_date"]: c for c in saved_cycles}

        # ── Compute FIFO for ALL cycles (correct labels) ──
        self._current_cycle_data = _fifo_allocate(all_cycles, self._current_all_txns) if all_cycles else []

        # Amount Due = sum of remaining from ALL previous cycles (excluding current)
        amount_due = 0
        today_str = date.today().isoformat()
        for cd in self._current_cycle_data:
            if cd["end"].isoformat() < today_str:  # previous cycle only
                amount_due += cd["remaining"]
        # Save default due date to card if not set
        if amount_due > 0 and not due_str:
            grace = card.get("grace_days", 20)
            due_str = _calc_due(card.get("statement_date", ""), grace)
            if due_str:
                self.cr.update(card["card_id"], due_date=due_str)
                card["due_date"] = due_str

        current_outstanding = balance

        stmt_display = _stmt_display(card.get("statement_date", ""))
        due_display = ""
        if due_str and "-" in due_str:
            try:
                due_display = date.fromisoformat(due_str).strftime("%d %b %Y")
            except:
                due_display = due_str
        else:
            due_display = "—"

        for label, value, color in [
            ("Limit", fmt_money(limit), "rgba(255,255,255,0.7)"),
            ("Statement", f"Every {stmt_display}", "rgba(255,255,255,0.9)"),
            ("Amount Due", fmt_money(amount_due), "#FCA5A5" if amount_due > 0 else "rgba(255,255,255,0.9)"),
            ("Due Date", due_display, "#FCA5A5" if amount_due > 0 else "rgba(255,255,255,0.9)"),
            ("Current Outstanding", fmt_money(current_outstanding), util_color),
        ]:
            c = QVBoxLayout(); c.setSpacing(0)
            c.addWidget(QLabel(f"<span style='color:rgba(255,255,255,0.5);font-size:9px;'>{label}</span>"))
            c.addWidget(QLabel(f"<b style='color:{color};font-size:13px;'>{value}</b>"))
            r2.addLayout(c)
        r2.addStretch()
        # Edit button — inline with metrics, right-aligned
        edit_btn = QPushButton("✏️  Edit Card")
        edit_btn.setStyleSheet("QPushButton{background:rgba(255,255,255,0.2);color:white;border:1px solid rgba(255,255,255,0.3);border-radius:6px;padding:4px 14px;font-size:11px;font-weight:700;}QPushButton:hover{background:rgba(255,255,255,0.35);}")
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.setFixedHeight(28)
        edit_btn.clicked.connect(lambda: self._edit_card(card))
        r2.addWidget(edit_btn)
        hdr_lay.addLayout(r2)
        self.header_lay.addWidget(hdr)
        self.header_container.show()

        # Statement info for cycle headers
        stmt_str = card.get("statement_date", "")
        grace = card.get("grace_days", 20)

        # ── Transactions with FIFO cycle headers (newest first) ──
        txn_scroll = QScrollArea(); txn_scroll.setWidgetResizable(True)
        txn_scroll.setFrameShape(QFrame.NoFrame)
        txn_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        txn_inner = QWidget(); txn_inner.setStyleSheet("background:transparent;")
        txn_lay = QVBoxLayout(txn_inner)
        txn_lay.setSpacing(4); txn_lay.setContentsMargins(0, 0, 0, 0)

        all_txns = self._current_all_txns
        cycle_data = self._current_cycle_data
        # saved_cycles already loaded above in hybrid section

        if not all_txns:
            nt = QLabel("No transactions found for this card.")
            nt.setStyleSheet(f"color:{C['text3']};font-size:12px;padding:20px;")
            nt.setAlignment(Qt.AlignCenter)
            txn_lay.addWidget(nt)
        elif not cycle_data:
            # No cycles (no statement_date) — flat list
            all_txns.sort(key=lambda t: (t["tx_date"], t.get("created_at", "")), reverse=True)
            by_date = OrderedDict()
            for tx in all_txns:
                d = tx["tx_date"]
                if d not in by_date: by_date[d] = []
                by_date[d].append(tx)
            for d_str, day_txns in by_date.items():
                try: txn_lay.addWidget(_day_header(date.fromisoformat(d_str).strftime("%A, %d %b")))
                except: txn_lay.addWidget(_day_header(d_str))
                for tx in day_txns:
                    txn_lay.addWidget(_tx_card(tx))
        else:
            # Group transactions by cycle_id for fast lookup
            # cycle_data is already newest first from _build_cycles
            # Assign each transaction to its cycle
            txn_by_cycle = {i: [] for i in range(len(cycle_data))}
            unassigned = []
            for tx in all_txns:
                tx_date = tx["tx_date"]
                assigned = False
                for i, cd in enumerate(cycle_data):
                    if cd["start"].isoformat() <= tx_date <= cd["end"].isoformat():
                        txn_by_cycle[i].append(tx)
                        assigned = True
                        break
                if not assigned:
                    unassigned.append(tx)

            # Show cycles newest first, skip empty
            for i, cd in enumerate(cycle_data):
                cycle_txns = txn_by_cycle.get(i, [])
                if not cycle_txns:
                    continue

                # Cycle header with FIFO stats + card gradient bg
                rem_color = "#059669" if cd["remaining"] <= 0 else ("#D97706" if cd["remaining"] <= cd["debits"] * 0.5 else "#DC2626")
                ch = QFrame()
                ch.setMinimumHeight(40)
                ch.setStyleSheet(f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {c1}22,stop:1 {c2}22);border:none;border-radius:8px;padding:6px 8px;")
                cl = QHBoxLayout(ch); cl.setContentsMargins(10, 4, 10, 4); cl.setSpacing(8)
                # Cycle name + statement ordinal
                cycle_name = _cycle_name(cd["start"])
                stmt_label = _stmt_display(stmt_str) if stmt_str else ""
                cl.addWidget(QLabel(f"<b style='color:{C['text']};'>📅 {cycle_name}  (stmt: {stmt_label})</b>"))
                cl.addStretch()
                cl.addWidget(QLabel(f"<span style='color:#DC2626;font-weight:700;'>Spent: {fmt_money(cd['debits'])}</span>"))
                if cd["paid"] > 0:
                    cl.addWidget(QLabel(f"<span style='color:#059669;font-weight:700;'>Paid: {fmt_money(cd['paid'])}</span>"))
                cl.addWidget(QLabel(f"<span style='color:{rem_color};font-weight:700;'>Remaining: {fmt_money(cd['remaining'])}</span>"))
                # Editable due date per cycle
                due_lbl = QLabel(f"<span style='color:{C['text3']};font-size:11px;'>Due:</span>")
                cl.addWidget(due_lbl)
                due_edit = QDateEdit(); due_edit.setCalendarPopup(True); due_edit.setDisplayFormat("dd MMM yyyy")
                due_edit.setFixedHeight(28); due_edit.setMinimumWidth(130)
                due_edit.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                due_edit.setStyleSheet(f"QDateEdit{{border:1px solid {C['border']};border-radius:4px;padding:2px 6px;font-size:11px;background:white;color:{C['text']};}}")
                # Get due_date: use from cycle data (hybrid), then DB lookup, then default
                saved_due = cd.get("due_date", "") or ""
                if not saved_due:
                    for sc in saved_cycles:
                        if sc.get("cycle_start_date","") == cd["start"].isoformat():
                            saved_due = sc.get("due_date","") or ""
                            break
                if not saved_due:
                    try: saved_due = (cd["end"] + timedelta(days=grace)).isoformat()
                    except: pass
                try:
                    due_edit.setDate(QDate.fromString(saved_due, "yyyy-MM-dd") if saved_due and "-" in saved_due else QDate.currentDate())
                except:
                    due_edit.setDate(QDate.currentDate())
                _cyc_cs = cd["start"].isoformat()
                def _save_cycle_due(d, cs=_cyc_cs):
                    for sc in saved_cycles:
                        if sc.get("cycle_start_date","") == cs:
                            self.cr.update_cycle(sc["cycle_id"], due_date=d.toString("yyyy-MM-dd"))
                            break
                due_edit.dateChanged.connect(_save_cycle_due)
                cl.addWidget(due_edit)
                txn_lay.addWidget(ch)

                # Group by date within cycle (newest first)
                by_date = OrderedDict()
                for tx in sorted(cycle_txns, key=lambda t: t["tx_date"], reverse=True):
                    d = tx["tx_date"]
                    if d not in by_date: by_date[d] = []
                    by_date[d].append(tx)
                for d_str, day_txns in by_date.items():
                    try: txn_lay.addWidget(_day_header(date.fromisoformat(d_str).strftime("%A, %d %b")))
                    except: txn_lay.addWidget(_day_header(d_str))
                    for tx in day_txns:
                        txn_lay.addWidget(_tx_card(tx))

            # Show unassigned transactions (before first cycle)
            if unassigned:
                unassigned_lbl = QLabel("<b>Earlier Transactions</b>")
                unassigned_lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;font-weight:700;padding:8px 0 4px 0;background:transparent;border:none;")
                txn_lay.addWidget(unassigned_lbl)
                for tx in sorted(unassigned, key=lambda t: t["tx_date"], reverse=True):
                    txn_lay.addWidget(_tx_card(tx))

        txn_lay.addStretch()
        txn_scroll.setWidget(txn_inner)
        self.details_lay.addWidget(txn_scroll, 1)
        self.details_container.show()

        self._populate_settle_footer(card)

    def _populate_settle_footer(self, card):
        aid = card["account_id"]
        balance = abs(self.bal.get_balance(aid))

        # Reuse cycle data already computed in _show_details (no extra DB query)
        amount_due = 0
        today_str = date.today().isoformat()
        for cd in getattr(self, '_current_cycle_data', []):
            if cd["end"].isoformat() < today_str:
                amount_due += cd["remaining"]

        self.sf_opt.blockSignals(True); self.sf_opt.clear()
        self.sf_opt.addItem(f"Amount Due — {fmt_money(amount_due)}", amount_due)
        self.sf_opt.addItem(f"Current Outstanding — {fmt_money(balance)}", balance)
        self.sf_opt.addItem("Custom Amount...", -1)
        self.sf_opt.blockSignals(False)

        self.sf_src.clear()
        for a in self.acct.list_active():
            if a["account_type"] != "CREDIT_CARD":
                self.sf_src.addItem(a["display_name"], a["account_id"])
        self.sf_custom_row.hide()
        self.settle_footer.show()

    def _on_sf_opt_changed(self, idx):
        self.sf_custom_row.setVisible(self.sf_opt.currentData() == -1)

    def _settle_from_footer(self):
        if not self._selected_card: return
        amt = self.sf_custom_amt.value() if self.sf_opt.currentData() == -1 else self.sf_opt.currentData()
        if not amt or amt <= 0:
            QMessageBox.warning(self, "Invalid", "Enter a valid positive amount."); return
        src_id = self.sf_src.currentData(); method = self.sf_method.currentText()
        if not src_id:
            QMessageBox.warning(self, "No Source", "Select a source account."); return
        card_name = self._selected_card.get("card_name", "Card")
        reply = QMessageBox.question(self, "Confirm Settlement",
            f"Settle {fmt_money(amt)} for {card_name}?\n\nFrom: {self.sf_src.currentText()}\nMethod: {method}",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes: return
        today = self.sf_date.date().toString("yyyy-MM-dd"); desc = f"Card settlement — {card_name}"; gid = str(uuid.uuid4())
        try:
            self.tx_repo.create(tx_date=today, account_id=src_id, pay_method=method, tx_type="DEBIT", amount=amt, description=desc, transaction_kind="TRANSFER", transfer_group_id=gid, category="transfer", pf_category="internal_transfer")
            self.tx_repo.create(tx_date=today, account_id=self._selected_card["account_id"], pay_method=method, tx_type="CREDIT", amount=amt, description=desc, transaction_kind="TRANSFER", transfer_group_id=gid, category="transfer", pf_category="internal_transfer")
            QMessageBox.information(self, "Done", f"Settlement of {fmt_money(amt)} recorded.")
            # Clear custom amount
            self.sf_custom_amt.setValue(0)
            self.sf_opt.setCurrentIndex(0)
            # Re-compute FIFO cycles into DB so reminders pick up new data
            self._save_cycles(self._selected_card)
            # Real-time update: refresh everything
            self._show_details(self._selected_card)
            self.reminders.load_reminders(self.cr.list_active())
            # Update carousel utilization
            ac = self.cr.list_active()
            self.carousel.load_cards(ac, self._utils(ac))
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Settlement failed: {e}")

    def _add_card(self):
        dlg = AddCardDialog(self.cr, self.acct, parent=self)
        dlg.card_added.connect(self.refresh)
        dlg.exec_()

    def _edit_card(self, card):
        dlg = AddCardDialog(self.cr, self.acct, card=card, parent=self)
        dlg.card_updated.connect(self.refresh)
        dlg.exec_()


    def refresh(self):
        self._selected_card = None; self.details_container.hide(); self.header_container.hide(); self.settle_footer.hide()
        self._load_cards()
