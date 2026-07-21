"""PDF export — Portrait A4, exact card replicas from app, no cell overflow."""
import uuid, hashlib, os, io, json
from datetime import datetime
from collections import OrderedDict

def generate_doc_id():
    return f"FM-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

def content_hash(data_str):
    return hashlib.sha256(data_str.encode()).hexdigest()[:16]

def watermark_text():
    return f"FinanceManager-{datetime.now().strftime('%Y%m%d%H%M%S')}"


def export_monthly_pdf(filepath, month_name, year,
                       summary, acct_data, acct_bal_map, all_accts, transactions,
                       chart_img_bytes=None, report_type="monthly"):
    """
    Parameters (all raw numbers, no pre-formatting):
        summary       : dict with keys credits, debits, net, transfers (floats)
        acct_data     : dict  account_id -> {"cr": float, "db": float}
        acct_bal_map  : dict  account_id -> {"start": float, "end": float}
        all_accts     : dict  account_id -> account row dict
        transactions  : list  of transaction dicts (from repo)
        report_type   : "monthly" or "filtered"
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
        from reportlab.lib.units import inch, mm
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                         Paragraph, Spacer, PageBreak, KeepTogether)
        from reportlab.graphics.shapes import Drawing, Rect, String, Circle
        from reportlab.graphics.charts.piecharts import Pie

        pw, ph = A4
        usable = pw - 72  # left+right margin
        doc_id = generate_doc_id()
        ts = datetime.now().strftime('%d %b %Y at %I:%M %p')
        tx_str = "".join(str(t.get("id", "")) for t in transactions)
        c_hash = content_hash(tx_str + doc_id + ts)
        wm = watermark_text()

        doc = SimpleDocTemplate(filepath, pagesize=A4,
                                topMargin=65, bottomMargin=70,
                                leftMargin=36, rightMargin=36)
        story = []
        S = getSampleStyleSheet()

        def ps(name, **kw):
            return ParagraphStyle(name, parent=S['Normal'], **kw)

        # Wrapping style for table cells
        WRAP = ps('wrap', fontSize=10, leading=13)
        WRAP_SM = ps('wrap_sm', fontSize=9, leading=11)
        WRAP_SM_R = ps('wrap_sm_r', fontSize=9, leading=11, alignment=TA_RIGHT)

        def _header(canvas, doc):
            canvas.saveState()
            canvas.setFillColor(colors.HexColor('#4F46E5'))
            canvas.rect(0, ph - 50, pw, 50, fill=True, stroke=False)
            canvas.setFillColor(colors.white)
            canvas.setFont('Helvetica-Bold', 15)
            canvas.drawString(30, ph - 28, 'Finance Manager')
            canvas.setFont('Helvetica', 9)
            # Truncate right header to prevent bleeding
            if report_type == "filtered":
                hdr_right = f'Filtered: {month_name}'
            else:
                hdr_right = f'{month_name} {year} Statement'
            if len(hdr_right) > 60:
                hdr_right = hdr_right[:57] + '...'
            canvas.drawRightString(pw - 30, ph - 28, hdr_right)
            canvas.setFont('Helvetica', 7)
            canvas.setFillColor(colors.Color(1, 1, 1, 0.7))
            canvas.drawString(30, ph - 14, f'Doc ID: {doc_id}')
            canvas.drawRightString(pw - 30, ph - 14, f'Generated: {ts}')
            canvas.restoreState()

        def _footer(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 36)
            canvas.setFillAlpha(0.06)
            canvas.setFillColor(colors.HexColor('#9CA3AF'))
            canvas.translate(pw / 2, ph / 2)
            canvas.rotate(45)
            canvas.drawCentredString(0, 0, wm)
            canvas.restoreState()
            canvas.saveState()
            canvas.setFillAlpha(1.0)
            canvas.setStrokeColor(colors.HexColor('#E5E7EB'))
            canvas.line(36, 52, pw - 36, 52)
            canvas.setFont('Helvetica', 7)
            canvas.setFillColor(colors.HexColor('#9CA3AF'))
            canvas.drawCentredString(pw / 2, 38, f'Page {doc.page}')
            canvas.drawString(36, 38, f'Hash: {c_hash}')
            canvas.drawRightString(pw - 36, 38, f'Doc ID: {doc_id}')
            canvas.setFont('Helvetica', 6)
            canvas.setFillColor(colors.HexColor('#D1D5DB'))
            canvas.drawCentredString(pw / 2, 24, 'Confidential — Finance Manager v3.0')
            canvas.restoreState()

        def _on_page(canvas, doc):
            _header(canvas, doc)
            _footer(canvas, doc)

        def section_hdr(text, color="#4F46E5"):
            t = Table([[Paragraph(f'<b><font color="white" size="13">{text}</font></b>', S['Normal'])]],
                      colWidths=[usable])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(color)),
                ('PADDING', (0, 0), (-1, -1), 12),
                ('ROUNDEDCORNERS', [8, 8, 8, 8]),
            ]))
            return t

        def fmt(v):
            """Format number with Indian-style commas."""
            if v is None:
                return "0.00"
            return f"{v:,.2f}"

        TYPE_COLORS = {
            "CURRENT": "#4F46E5", "WALLET": "#8B5CF6",
            "CASH": "#F59E0B", "CREDIT_CARD": "#EF4444",
        }
        TYPE_LABELS = {
            "CURRENT": "Bank Account", "WALLET": "Wallet",
            "CASH": "Cash", "CREDIT_CARD": "Credit Card",
        }

        # ════════════════════════════════════════
        # SECTION 1: MONTHLY SUMMARY
        # ════════════════════════════════════════
        story.append(Spacer(1, 10))
        section_title = f"Summary — {month_name}" if report_type == "filtered" else f"Monthly Summary — {month_name} {year}"
        story.append(section_hdr(section_title))
        story.append(Spacer(1, 14))

        cr = summary.get("credits", 0)
        db_t = summary.get("debits", 0)
        net = summary.get("net", 0)
        tr = summary.get("transfers", 0)

        kw = usable / 5
        kpi_items = [
            ("TRANSACTIONS", f"{len(transactions)}", "#4F46E5"),
            ("CREDITS", fmt(cr), "#059669"),
            ("DEBITS", fmt(db_t), "#DC2626"),
            ("NET", fmt(net), "#059669" if net >= 0 else "#DC2626"),
            ("TRANSFERS", fmt(tr), "#8B5CF6"),
        ]
        kpi_data = [[
            Paragraph(f'<font size="8" color="#6B7280">{lbl}</font><br/>'
                      f'<b><font size="15" color="{col}">{val}</font></b>', S['Normal'])
            for lbl, val, col in kpi_items
        ]]
        kpi = Table(kpi_data, colWidths=[kw]*5, rowHeights=[60])
        kpi.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
            ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#F3F4F6')),
            ('PADDING', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(kpi)
        story.append(Spacer(1, 18))

        # ── Account Summary — EXACT CARD REPLICA ──
        story.append(Paragraph('<b style="font-size:15px;">Account Summary</b>',
                               ps('h', fontSize=15, textColor=colors.HexColor('#111827'))))
        story.append(Spacer(1, 10))

        # Group accounts by type
        type_groups = {"CURRENT": [], "WALLET": [], "CASH": [], "CREDIT_CARD": []}
        for aid, info in acct_data.items():
            a = all_accts.get(aid)
            if not a:
                continue
            at = a.get("account_type", "CURRENT")
            if at not in type_groups:
                type_groups[at] = []
            bal = acct_bal_map.get(aid, {"start": 0, "end": 0})
            type_groups[at].append({
                "name": a.get("display_name", aid),
                "cr": info["cr"], "db": info["db"],
                "start": bal["start"], "end": bal["end"], "type": at,
            })

        for atype in ["CURRENT", "WALLET", "CASH", "CREDIT_CARD"]:
            accts = type_groups.get(atype, [])
            if not accts:
                continue

            type_color = TYPE_COLORS.get(atype, "#6B7280")
            type_label = TYPE_LABELS.get(atype, atype)

            th = Table([[Paragraph(f'<font color="white" size="11"><b>{type_label}</b></font>', S['Normal'])]],
                       colWidths=[usable])
            th.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(type_color)),
                ('PADDING', (0, 0), (-1, -1), 8),
                ('ROUNDEDCORNERS', [6, 6, 6, 6]),
            ]))
            story.append(th)
            story.append(Spacer(1, 6))

            for a in accts:
                net_val = a["cr"] - a["db"]
                net_color = "#059669" if net_val >= 0 else "#DC2626"

                card_data = [
                    [Paragraph(f'<b><font size="12" color="#111827">{a["name"]}</font></b>', S['Normal']),
                     Paragraph(f'<font size="9" color="{type_color}"><b>{type_label}</b></font>', S['Normal'])],
                    [Paragraph(f'<font size="9" color="#6B7280">Start: </font><font size="10" color="#374151"><b>{fmt(a["start"])}</b></font>', S['Normal']),
                     Paragraph(f'<font size="9" color="#6B7280">End: </font><font size="10" color="{net_color}"><b>{fmt(a["end"])}</b></font>', S['Normal'])],
                    [Paragraph(f'<font size="9" color="#6B7280">Credits: </font><font color="#059669"><b>{fmt(a["cr"])}</b></font>', S['Normal']),
                     Paragraph(f'<font size="9" color="#6B7280">Debits: </font><font color="#DC2626"><b>{fmt(a["db"])}</b></font>', S['Normal'])],
                    [Paragraph(f'<font size="9" color="#6B7280">Net: </font><font size="12" color="{net_color}"><b>{fmt(net_val)}</b></font>', S['Normal']),
                     Paragraph('', S['Normal'])],
                ]
                cw = usable * 0.55, usable * 0.45
                card = Table(card_data, colWidths=cw)
                card.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
                    ('LINEAFTER', (0, 0), (0, -1), 4, colors.HexColor(type_color)),
                    ('PADDING', (0, 0), (-1, -1), 10),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('ROUNDEDCORNERS', [8, 8, 8, 8]),
                ]))
                story.append(KeepTogether([card, Spacer(1, 6)]))

        # ════════════════════════════════════════
        # SECTION 2: VISUALIZATION (page break)
        # ════════════════════════════════════════
        story.append(PageBreak())
        story.append(Spacer(1, 10))
        viz_title = f"Data Visualization — {month_name}" if report_type == "filtered" else f"Data Visualization — {month_name} {year}"
        story.append(section_hdr(viz_title, "#059669"))
        story.append(Spacer(1, 12))

        cats = {}
        for t in transactions:
            if t["tx_type"] == "DEBIT":
                cn = t.get("cat_name") or "Other"
                cats[cn] = cats.get(cn, 0) + t["amount"]

        if cats:
            story.append(Paragraph('<b>Expense by Category</b>',
                                   ps('h', fontSize=13, textColor=colors.HexColor('#374151'))))
            story.append(Spacer(1, 8))
            cat_colors = ['#4F46E5','#10B981','#F59E0B','#EF4444','#8B5CF6','#EC4899','#06B6D4','#F97316','#14B8A6','#6366F1']
            sorted_cats = sorted(cats.items(), key=lambda x: x[1], reverse=True)
            total_spend = sum(cats.values())

            d = Drawing(usable, 260)
            d.add(Rect(0, 0, usable, 260, fillColor=colors.HexColor('#F8FAFC'),
                       strokeColor=colors.HexColor('#E5E7EB'), strokeWidth=0.5, rx=12, ry=12))
            pie = Pie()
            pie.x = 30; pie.y = 30; pie.width = 190; pie.height = 190
            pie.data = [v for _, v in sorted_cats]
            pie.labels = None
            pie.slices.strokeWidth = 2; pie.slices.strokeColor = colors.white
            for i in range(len(sorted_cats)):
                pie.slices[i].fillColor = colors.HexColor(cat_colors[i % len(cat_colors)])
            d.add(pie)
            lx, ly = 260, 20
            for i, (name, val) in enumerate(sorted_cats[:12]):
                pct = val / total_spend * 100 if total_spend > 0 else 0
                d.add(Rect(lx, ly + i * 19, 10, 10, fillColor=colors.HexColor(cat_colors[i % len(cat_colors)]), rx=2, ry=2))
                d.add(String(lx + 16, ly + i * 19, f"{name}: {val:,.0f} ({pct:.1f}%)", fontSize=9))
            story.append(d)

        # Need vs Want
        need = sum(t["amount"] for t in transactions if t.get("neednwant") == 1 and t["tx_type"] == "DEBIT")
        want = sum(t["amount"] for t in transactions if t.get("neednwant") == 0 and t["tx_type"] == "DEBIT")
        total_nw = need + want
        if total_nw > 0:
            story.append(Spacer(1, 14))
            story.append(Paragraph('<b>Need vs Want</b>',
                                   ps('h', fontSize=13, textColor=colors.HexColor('#374151'))))
            story.append(Spacer(1, 8))
            need_pct = need / total_nw * 100
            want_pct = want / total_nw * 100
            nw_data = [[
                Paragraph(f'<font size="9" color="#6B7280">NEED</font><br/><b><font size="16" color="#4F46E5">{need:,.0f}</font><font size="10" color="#6B7280"> ({need_pct:.0f}%)</font></b>', S['Normal']),
                Paragraph(f'<font size="9" color="#6B7280">WANT</font><br/><b><font size="16" color="#F59E0B">{want:,.0f}</font><font size="10" color="#6B7280"> ({want_pct:.0f}%)</font></b>', S['Normal']),
                Paragraph(f'<font size="9" color="#6B7280">TOTAL</font><br/><b><font size="16" color="#111827">{total_nw:,.0f}</font></b>', S['Normal']),
            ]]
            nw_tbl = Table(nw_data, colWidths=[usable/3]*3, rowHeights=[60])
            nw_tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
                ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#F3F4F6')),
                ('PADDING', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(nw_tbl)

        # ════════════════════════════════════════
        # SECTION 3: TRANSACTIONS (page break)
        # ════════════════════════════════════════
        story.append(PageBreak())
        story.append(Spacer(1, 10))
        tx_section_title = f"Transaction Details — {month_name}" if report_type == "filtered" else f"Transaction Details — {month_name} {year}"
        story.append(section_hdr(tx_section_title, "#F59E0B"))
        story.append(Spacer(1, 8))
        story.append(Paragraph(f'<font size="10" color="#6B7280">{len(transactions)} transactions</font>', S['Normal']))
        story.append(Spacer(1, 8))

        # Group by date
        by_date = OrderedDict()
        for tx in sorted(transactions, key=lambda t: t["tx_date"], reverse=True):
            d = tx["tx_date"]
            if d not in by_date: by_date[d] = []
            by_date[d].append(tx)

        cat_icons = {
            "food_dining": "\U0001f354", "transport": "\U0001f697", "shopping": "\U0001f6cd\ufe0f",
            "bills_utilities": "\U0001f4a1", "rent": "\U0001f3e0", "salary": "\U0001f4b0",
            "investment": "\U0001f4c8", "health": "\U0001f3e5", "education": "\U0001f4da",
            "entertainment": "\U0001f3ac", "transfer": "\U0001f504", "other": "\U0001f4cb",
        }

        for tx_date, txns_day in by_date.items():
            try:
                from datetime import date as dt_cls
                dy = dt_cls.fromisoformat(tx_date)
                day_label = dy.strftime("%A, %d %B %Y")
            except:
                day_label = tx_date

            # Date header
            dh = Table([[Paragraph(f'<b><font color="white" size="10">{day_label}</font></b>', S['Normal'])]],
                       colWidths=[usable])
            dh.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#374151')),
                ('PADDING', (0, 0), (-1, -1), 8),
                ('ROUNDEDCORNERS', [6, 6, 6, 6]),
            ]))
            story.append(dh)
            story.append(Spacer(1, 6))

            for tx in txns_day:
                tx_type = tx.get("tx_type", "")
                kind = tx.get("transaction_kind", "REGULAR")
                amount = tx.get("amount", 0)

                if kind == "TRANSFER":
                    amt_color = colors.HexColor('#6B7280')
                    prefix = "\u2212" if tx_type == "DEBIT" else "+"
                    type_label = f"Transfer ({tx_type})"
                elif tx_type == "DEBIT":
                    amt_color = colors.HexColor('#EF4444')
                    prefix = "\u2212"
                    type_label = "DEBIT"
                else:
                    amt_color = colors.HexColor('#059669')
                    prefix = "+"
                    type_label = "CREDIT"

                cat_id = tx.get("category") or "other"
                icon = cat_icons.get(cat_id, "\U0001f4cb")
                person = tx.get("person_org") or ""
                desc = tx.get("description") or ""
                if person and desc: main_text = f"{person} \u2014 {desc}"
                elif person: main_text = person
                elif desc: main_text = desc
                else: main_text = "No description"

                cat_name = tx.get("cat_name") or "\u2014"
                method_name = tx.get("method_name") or "\u2014"
                acct_name = tx.get("account_name") or "\u2014"

                # Card-style: left description + right amount
                card_data = [[
                    Paragraph(
                        f'<font size="11"><b>{icon}  {main_text}</b></font><br/>'
                        f'<font size="9" color="#6B7280">{cat_name}  \u00b7  {method_name}  \u00b7  {acct_name}</font>',
                        WRAP),
                    Paragraph(
                        f'<font size="13"><b>{prefix}{fmt(amount)}</b></font><br/>'
                        f'<font size="9" color="#6B7280"><b>{type_label}</b></font>',
                        WRAP_SM_R),
                ]]
                card = Table(card_data, colWidths=[usable - 120, 110])
                card.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F9FAFB')),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('LEFTPADDING', (0, 0), (-1, -1), 12),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                    ('LINEBEFORE', (0, 0), (0, -1), 3, amt_color),
                ]))
                story.append(KeepTogether([card, Spacer(1, 4)]))

        # ════════════════════════════════════════
        # SECTION 4: VERIFICATION (page break)
        # ════════════════════════════════════════
        story.append(PageBreak())
        story.append(Spacer(1, 10))
        story.append(section_hdr("Document Verification", "#4F46E5"))
        story.append(Spacer(1, 20))

        try:
            import qrcode as qr_mod
            # QR contains: document ID, hash, period, totals — scannable & verifiable
            qr_data = (
                f"Finance Manager Statement\n"
                f"Doc ID: {doc_id}\n"
                f"Period: {month_name}\n" if report_type == "filtered" else f"Period: {month_name} {year}\n"
                f"Transactions: {len(transactions)}\n"
                f"Total Credits: {summary.get('credits', 0):,.2f}\n"
                f"Total Debits: {summary.get('debits', 0):,.2f}\n"
                f"Net: {summary.get('net', 0):,.2f}\n"
                f"Hash: {c_hash}\n"
                f"Generated: {ts}"
            )
            qr_obj = qr_mod.QRCode(version=4, box_size=6, border=2,
                                    error_correction=qr_mod.constants.ERROR_CORRECT_M)
            qr_obj.add_data(qr_data)
            qr_obj.make(fit=True)
            img = qr_obj.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
            from reportlab.platypus import Image as RLImage
            qr_img = RLImage(buf, width=200, height=200)
            qr_table = Table([[qr_img]], colWidths=[usable])
            qr_table.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
            story.append(qr_table)
            story.append(Spacer(1, 16))
        except:
            story.append(Paragraph('<i>QR requires: pip install qrcode</i>', S['Normal']))
            story.append(Spacer(1, 16))

        verify_data = [
            ['Document ID', doc_id],
            ['Content Hash (SHA-256)', c_hash],
            ['Generated', ts],
            ['Transactions', str(len(transactions))],
            ['Period', f'{month_name}'] if report_type == 'filtered' else ['Period', f'{month_name} {year}'],
        ]
        vtbl = Table(verify_data, colWidths=[3*inch, 4*inch])
        vtbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
            ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#E5E7EB')),
            ('PADDING', (0, 0), (-1, -1), 12),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
        ]))
        story.append(vtbl)

        doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
        return doc_id

    except ImportError:
        return None


def export_detail_pdf(filepath, title, status, info_pairs, analysis_pairs, sections=None):
    """Generic detail PDF with security features (QR, hash, watermark)."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_RIGHT
        from reportlab.lib.units import inch
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                         Paragraph, Spacer, PageBreak, KeepTogether)

        pw, ph = A4
        usable = pw - 72
        doc_id = generate_doc_id()
        ts = datetime.now().strftime('%d %b %Y at %I:%M %p')
        raw = "".join(str(v) for _, v in info_pairs) + doc_id + ts
        c_hash = content_hash(raw)
        wm = watermark_text()
        doc = SimpleDocTemplate(filepath, pagesize=A4, topMargin=65, bottomMargin=70,
                                leftMargin=36, rightMargin=36)
        story = []
        S = getSampleStyleSheet()

        def ps(n, **kw):
            return ParagraphStyle(n, parent=S['Normal'], **kw)

        WRAP = ps('dw', fontSize=10, leading=13)
        WRAP_SM_R = ps('dsmr', fontSize=9, leading=11, alignment=TA_RIGHT)
        ST_COLORS = {'ACTIVE': '#4F46E5', 'OVERDUE': '#DC2626', 'PARTIALLY_PAID': '#D97706',
                     'REPAID': '#059669', 'CLOSED': '#059669', 'MATURED': '#059669',
                     'WITHDRAWN': '#6B7280', 'CLEARED': '#059669'}

        def _header(canvas, doc):
            canvas.saveState()
            canvas.setFillColor(colors.HexColor('#4F46E5'))
            canvas.rect(0, ph - 50, pw, 50, fill=True, stroke=False)
            canvas.setFillColor(colors.white)
            canvas.setFont('Helvetica-Bold', 15)
            canvas.drawString(30, ph - 28, 'Finance Manager')
            canvas.setFont('Helvetica', 9)
            r = title[:57] + '...' if len(title) > 60 else title
            canvas.drawRightString(pw - 30, ph - 28, r)
            canvas.setFont('Helvetica', 7)
            canvas.setFillColor(colors.Color(1, 1, 1, 0.7))
            canvas.drawString(30, ph - 14, f'Doc ID: {doc_id}')
            canvas.drawRightString(pw - 30, ph - 14, f'Generated: {ts}')
            canvas.restoreState()

        def _footer(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 36)
            canvas.setFillAlpha(0.06)
            canvas.setFillColor(colors.HexColor('#9CA3AF'))
            canvas.translate(pw / 2, ph / 2)
            canvas.rotate(45)
            canvas.drawCentredString(0, 0, wm)
            canvas.restoreState()
            canvas.saveState()
            canvas.setFillAlpha(1.0)
            canvas.setStrokeColor(colors.HexColor('#E5E7EB'))
            canvas.line(36, 52, pw - 36, 52)
            canvas.setFont('Helvetica', 7)
            canvas.setFillColor(colors.HexColor('#9CA3AF'))
            canvas.drawCentredString(pw / 2, 38, f'Page {doc.page}')
            canvas.drawString(36, 38, f'Hash: {c_hash}')
            canvas.drawRightString(pw - 36, 38, f'Doc ID: {doc_id}')
            canvas.setFont('Helvetica', 6)
            canvas.setFillColor(colors.HexColor('#D1D5DB'))
            canvas.drawCentredString(pw / 2, 24, 'Confidential \u2014 Finance Manager v3.0')
            canvas.restoreState()

        def _on_page(canvas, doc):
            _header(canvas, doc)
            _footer(canvas, doc)

        def shdr(text, color="#4F46E5"):
            t = Table([[Paragraph(f'<b><font color="white" size="13">{text}</font></b>', S['Normal'])]],
                      colWidths=[usable])
            t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(color)),
                                    ('PADDING', (0, 0), (-1, -1), 12), ('ROUNDEDCORNERS', [8, 8, 8, 8])]))
            return t

        def fmt(v):
            return f"{v:,.2f}" if v is not None else "0.00"

        # Title + status badge
        story.append(Spacer(1, 10))
        sc = ST_COLORS.get((status or '').upper(), '#6B7280')
        tr = Table([[
            Paragraph(f'<b><font size="16" color="#111827">{title}</font></b>', S['Normal']),
            Paragraph(f'<font color="white" size="11"><b>{status}</b></font>', S['Normal']),
        ]], colWidths=[usable - 120, 120])
        tr.setStyle(TableStyle([('BACKGROUND', (1, 0), (1, 0), colors.HexColor(sc)),
                                 ('ALIGN', (1, 0), (1, 0), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                 ('ROUNDEDCORNERS', [6, 6, 6, 6]),
                                 ('BOTTOMPADDING', (0, 0), (-1, -1), 8), ('TOPPADDING', (0, 0), (-1, -1), 8)]))
        story.append(tr)
        story.append(Spacer(1, 14))

        # Info card
        if info_pairs:
            idata = [[Paragraph(f'<font size="9" color="#6B7280">{l}</font>', S['Normal']),
                       Paragraph(f'<b><font size="11" color="#111827">{v}</font></b>', S['Normal'])]
                      for l, v in info_pairs]
            it = Table(idata, colWidths=[usable * 0.35, usable * 0.65])
            it.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
                                     ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
                                     ('LINEBEFORE', (0, 0), (0, -1), 4, colors.HexColor('#4F46E5')),
                                     ('PADDING', (0, 0), (-1, -1), 10), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                     ('ROUNDEDCORNERS', [8, 8, 8, 8])]))
            story.append(it)
            story.append(Spacer(1, 14))

        # Analysis KPIs
        if analysis_pairs:
            cell_w = usable / 5
            kpi_rows = []
            for ri in range(0, len(analysis_pairs), 5):
                cells = []
                for ci in range(5):
                    idx = ri + ci
                    if idx < len(analysis_pairs):
                        lbl, val = analysis_pairs[idx]
                        cells.append(Paragraph(
                            f'<font size="7" color="#6B7280">{lbl}</font><br/>'
                            f'<b><font size="11" color="#4F46E5">{val}</font></b>', S['Normal']))
                    else:
                        cells.append(Paragraph('', S['Normal']))
                kpi_rows.append(cells)
            kpi = Table(kpi_rows, colWidths=[cell_w] * 5, rowHeights=[45] * len(kpi_rows))
            kpi.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
                ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#F3F4F6')),
                ('PADDING', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(kpi)
            story.append(Spacer(1, 16))

        # Data sections
        for sec in (sections or []):
            story.append(shdr(sec.get("title", ""), sec.get("color", "#4F46E5")))
            story.append(Spacer(1, 8))
            sd = sec.get("data", [])
            st = sec.get("type", "repayment")
            ACT = {'Paid': '#059669', 'Extra Paid': '#4F46E5', 'Partially Paid': '#D97706',
                    'Missed': '#DC2626', 'Upcoming': '#6B7280'}

            if st == "repayment":
                for r in sd:
                    cd = [[Paragraph(f'<font size="11"><b>{r.get("date","")}</b></font><br/><font size="9" color="#6B7280">{r.get("description","")}</font>', WRAP),
                           Paragraph(f'<font size="13"><b>{fmt(r.get("amount",0))}</b></font>', WRAP_SM_R)]]
                    c = Table(cd, colWidths=[usable - 120, 110])
                    c.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F9FAFB')),
                                            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
                                            ('TOPPADDING', (0,0), (-1,-1), 8), ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                                            ('LEFTPADDING', (0,0), (-1,-1), 12), ('RIGHTPADDING', (0,0), (-1,-1), 12),
                                            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (1,0), (1,0), 'RIGHT'),
                                            ('LINEBEFORE', (0,0), (0,-1), 3, colors.HexColor('#4F46E5'))]))
                    story.append(KeepTogether([c, Spacer(1, 4)]))

            elif st == "amort":
                for r in sd:
                    cd = [[Paragraph(f'<b><font size="11">Month {r.get("month","")}</font></b>', WRAP), Paragraph('', WRAP)],
                          [Paragraph(f'<font size="9" color="#6B7280">EMI</font><br/><b>{fmt(r.get("emi",0))}</b>', WRAP),
                           Paragraph(f'<font size="9" color="#6B7280">Principal</font><br/><b>{fmt(r.get("principal",0))}</b>', WRAP),
                           Paragraph(f'<font size="9" color="#6B7280">Interest</font><br/><b>{fmt(r.get("interest",0))}</b>', WRAP),
                           Paragraph(f'<font size="9" color="#6B7280">Balance</font><br/><b>{fmt(r.get("balance",0))}</b>', WRAP)]]
                    c = Table(cd, colWidths=[usable * 0.25] * 4)
                    c.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F9FAFB')),
                                            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
                                            ('SPAN', (0,0), (-1,0)),
                                            ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                                            ('LEFTPADDING', (0,0), (-1,-1), 10), ('RIGHTPADDING', (0,0), (-1,-1), 10),
                                            ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
                    story.append(KeepTogether([c, Spacer(1, 3)]))

            elif st == "amort_actuals":
                for r in sd:
                    sst = r.get("status", "Upcoming")
                    sc2 = ACT.get(sst, '#6B7280')
                    cd = [[Paragraph(f'<b><font size="11">Month {r.get("month","")} \u00b7 {r.get("date","")}</font></b>', WRAP),
                           Paragraph(f'<font color="white" size="10"><b>{sst}</b></font>', WRAP_SM_R)],
                          [Paragraph(f'<font size="9" color="#6B7280">Planned EMI</font><br/><b>{fmt(r.get("p_emi",0))}</b>', WRAP),
                           Paragraph(f'<font size="9" color="#6B7280">Actual Paid</font><br/><b>{fmt(r.get("a_paid",0))}</b>', WRAP),
                           Paragraph(f'<font size="9" color="#6B7280">Planned Bal</font><br/><b>{fmt(r.get("p_bal",0))}</b>', WRAP),
                           Paragraph(f'<font size="9" color="#6B7280">Actual Bal</font><br/><b>{fmt(r.get("a_bal",0))}</b>', WRAP)]]
                    c = Table(cd, colWidths=[usable * 0.25] * 4)
                    c.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F9FAFB')),
                                            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
                                            ('SPAN', (0,0), (1,0)),
                                            ('BACKGROUND', (1,0), (1,0), colors.HexColor(sc2)),
                                            ('ALIGN', (1,0), (1,0), 'CENTER'),
                                            ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                                            ('LEFTPADDING', (0,0), (-1,-1), 10), ('RIGHTPADDING', (0,0), (-1,-1), 10),
                                            ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
                    story.append(KeepTogether([c, Spacer(1, 3)]))

            elif st == "mf_txn":
                for r in sd:
                    cd = [[Paragraph(f'<font size="11"><b>{r.get("type","")} \u00b7 {r.get("date","")}</b></font><br/><font size="9" color="#6B7280">NAV: {r.get("nav",0):,.4f}  \u00b7  Units: {r.get("units",0):,.4f}</font>', WRAP),
                           Paragraph(f'<font size="13"><b>{fmt(r.get("amount",0))}</b></font>', WRAP_SM_R)]]
                    c = Table(cd, colWidths=[usable - 120, 110])
                    c.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F9FAFB')),
                                            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
                                            ('TOPPADDING', (0,0), (-1,-1), 8), ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                                            ('LEFTPADDING', (0,0), (-1,-1), 12), ('RIGHTPADDING', (0,0), (-1,-1), 12),
                                            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (1,0), (1,0), 'RIGHT'),
                                            ('LINEBEFORE', (0,0), (0,-1), 3, colors.HexColor('#4F46E5'))]))
                    story.append(KeepTogether([c, Spacer(1, 4)]))
            story.append(Spacer(1, 10))

        # Verification page
        story.append(PageBreak())
        story.append(Spacer(1, 10))
        story.append(shdr("Document Verification"))
        story.append(Spacer(1, 20))
        try:
            import qrcode as qr_mod
            qr_data = f"Finance Manager Detail\nDoc ID: {doc_id}\nTitle: {title}\nStatus: {status}\nHash: {c_hash}\nGenerated: {ts}"
            qr_obj = qr_mod.QRCode(version=4, box_size=6, border=2, error_correction=qr_mod.constants.ERROR_CORRECT_M)
            qr_obj.add_data(qr_data); qr_obj.make(fit=True)
            img = qr_obj.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
            from reportlab.platypus import Image as RLImage
            qi = RLImage(buf, width=200, height=200)
            qt = Table([[qi]], colWidths=[usable])
            qt.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
            story.append(qt)
            story.append(Spacer(1, 16))
        except Exception:
            story.append(Spacer(1, 16))
        vd = [['Document ID', doc_id], ['Content Hash (SHA-256)', c_hash],
              ['Generated', ts], ['Title', title], ['Status', status or '']]
        vt = Table(vd, colWidths=[3 * inch, 4 * inch])
        vt.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
                                  ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
                                  ('INNERGRID', (0,0), (-1,-1), 0.3, colors.HexColor('#E5E7EB')),
                                  ('PADDING', (0,0), (-1,-1), 12),
                                  ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                                  ('FONTSIZE', (0,0), (-1,-1), 11)]))
        story.append(vt)
        doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
        return doc_id
    except ImportError:
        return None
