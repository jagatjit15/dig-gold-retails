"""Black-and-white friendly GST tax invoice PDF (ReportLab)."""
from datetime import datetime
from io import BytesIO
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

pdfmetrics.registerFont(TTFont("Cormorant-Bold",
                               str(Path(__file__).parent / "fonts" / "CormorantGaramond-Bold.ttf")))

ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
        "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
        "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n: int) -> str:
    return ONES[n] if n < 20 else (TENS[n // 10] + (" " + ONES[n % 10] if n % 10 else ""))


def _three(n: int) -> str:
    h, r = divmod(n, 100)
    return " ".join(p for p in [f"{ONES[h]} Hundred" if h else "", _two(r) if r else ""] if p)


def num_to_words(n: int) -> str:
    if n == 0:
        return "Zero"
    parts = []
    for div, name in [(10**7, "Crore"), (10**5, "Lakh"), (1000, "Thousand")]:
        q, n = divmod(n, div)
        if q:
            parts.append(f"{num_to_words(q) if q > 99 else _two(q)} {name}")
    if n:
        parts.append(_three(n))
    return " ".join(parts)


def amount_in_words(x: float) -> str:
    rupees = int(round(x * 100)) // 100
    paise = int(round(x * 100)) % 100
    s = f"Rupees {num_to_words(rupees)}"
    if paise:
        s += f" and {_two(paise)} Paise"
    return s + " Only"


def _m(v: float) -> str:
    neg, v = v < 0, abs(v)
    whole, frac = f"{v:.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
        whole = f"{head},{tail}"
    return f"{'-' if neg else ''}{whole}.{frac}"


def build_invoice_pdf(bill: dict, branch: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm,
                            title=f"Tax Invoice {bill['bill_no']}")
    s = ParagraphStyle("s", fontName="Helvetica", fontSize=8.5, leading=11)
    sb = ParagraphStyle("sb", parent=s, fontName="Helvetica-Bold")
    shop = ParagraphStyle("shop", fontName="Cormorant-Bold", fontSize=22, leading=26)
    title = ParagraphStyle("t", fontName="Cormorant-Bold", fontSize=15, leading=18, alignment=2)
    grid = [("GRID", (0, 0), (-1, -1), 0.5, colors.black)]
    inter = bill.get("igst", 0) > 0
    created = datetime.fromisoformat(bill["created_at"]).strftime("%d-%m-%Y %H:%M")

    head = Table([[
        [Paragraph(branch["name"], shop),
         Paragraph(branch.get("address") or "", s),
         Paragraph(f"GSTIN: {branch.get('gstin') or '-'} &nbsp; State Code: "
                   f"{branch.get('state_code') or '-'}", s)],
        [Paragraph("TAX INVOICE", title),
         Paragraph(f"Invoice No: <b>{bill['bill_no']}</b>", ParagraphStyle("r", parent=s, alignment=2)),
         Paragraph(f"Date: {created}", ParagraphStyle("r2", parent=s, alignment=2))],
    ]], colWidths=[116 * mm, 70 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))

    pos = bill.get("customer_state_code") or branch.get("state_code") or "-"
    cust = Table([[
        [Paragraph("Bill To", sb), Paragraph(bill["customer_name"], s),
         Paragraph(bill.get("customer_address") or "", s),
         Paragraph(f"Phone: {bill.get('customer_phone') or '-'}", s),
         Paragraph(f"GSTIN: {bill.get('customer_gstin') or 'Unregistered'}", s)],
        [Paragraph(f"Place of Supply (State Code): {pos}", s),
         Paragraph(f"Supply type: {'Inter-state (IGST)' if inter else 'Intra-state (CGST + SGST)'}", s),
         Paragraph(f"Payment mode: {bill.get('payment_mode', 'cash').upper()}", s)],
    ]], colWidths=[100 * mm, 86 * mm])
    cust.setStyle(TableStyle(grid + [("VALIGN", (0, 0), (-1, -1), "TOP")]))

    rows = [["#", "Item / HUID", "HSN", "Purity", "Gross g", "Net g", "Rate/g",
             "Metal", "Making", "Taxable"]]
    for i, ln in enumerate(bill["lines"], 1):
        desc = ln["tag_id"] + (f"<br/>HUID {ln['huid']}" if ln.get("huid") else "")
        rows.append([str(i), Paragraph(desc, s), ln.get("hsn_code") or "-", ln["purity_code"],
                     f"{ln.get('gross_wt', 0):.3f}", f"{ln['net_wt']:.3f}",
                     _m(ln["rate_per_gram"]), _m(ln["metal_value"]),
                     _m(ln["making_charge"]), _m(ln["taxable"])])
    lines = Table(rows, repeatRows=1, colWidths=[7 * mm, 38 * mm, 13 * mm, 15 * mm, 16 * mm,
                                                 16 * mm, 19 * mm, 21 * mm, 19 * mm, 22 * mm])
    lines.setStyle(TableStyle(grid + [
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6E6E6")),
        ("ALIGN", (4, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))

    rate = bill["lines"][0].get("gst_rate", 3.0) if bill["lines"] else 3.0
    tot = [["Taxable value", _m(bill["subtotal"])]]
    if inter:
        tot.append([f"IGST @ {rate:g}%", _m(bill["igst"])])
    else:
        tot += [[f"CGST @ {rate / 2:g}%", _m(bill["cgst"])], [f"SGST @ {rate / 2:g}%", _m(bill["sgst"])]]
    tot += [["Round off", _m(bill.get("round_off", 0))], ["Invoice total (Rs.)", _m(bill["grand_total"])]]
    totals = Table(tot, colWidths=[45 * mm, 32 * mm], hAlign="RIGHT")
    totals.setStyle(TableStyle(grid + [("ALIGN", (1, 0), (1, -1), "RIGHT"),
                                       ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                                       ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 10)]))

    old = bill.get("old_gold") or []
    payable = bill.get("net_payable")
    payable = bill["grand_total"] if payable is None else payable
    old_parts = []
    if old:
        orows = [["Old gold / exchange", "Fineness", "Gross g", "Net g", "Fine g", "Deduct %", "Value"]]
        orows += [[Paragraph(o["description"], s), f"{o['fineness']:.3f}", f"{o['gross_wt']:.3f}",
                   f"{o['net_wt']:.3f}", f"{o['fine_wt']:.3f}", f"{o['deduction_pct']:g}",
                   _m(o["value"])] for o in old]
        ot = Table(orows, colWidths=[56 * mm, 20 * mm, 20 * mm, 20 * mm, 20 * mm, 18 * mm, 32 * mm])
        ot.setStyle(TableStyle(grid + [("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
                                       ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
                                       ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6E6E6")),
                                       ("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
        net = Table([["Less: old gold value", _m(-bill.get("old_gold_total", 0))],
                     ["Net payable (Rs.)", _m(payable)]], colWidths=[45 * mm, 32 * mm], hAlign="RIGHT")
        net.setStyle(TableStyle(grid + [("ALIGN", (1, 0), (1, -1), "RIGHT"),
                                        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                                        ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 10)]))
        old_parts = [Spacer(1, 4 * mm), ot, Spacer(1, 3 * mm), net]

    sign = Table([[Paragraph("Certified that the particulars given above are true and correct. "
                             "Weights in grams. Goods once sold are subject to the shop's exchange policy.", s),
                   Paragraph(f"For {branch['name']}<br/><br/><br/>Authorised Signatory",
                             ParagraphStyle("sg", parent=s, alignment=2))]],
                 colWidths=[116 * mm, 70 * mm])
    doc.build([head, Spacer(1, 4 * mm), cust, Spacer(1, 4 * mm), lines, Spacer(1, 3 * mm),
               totals, *old_parts, Spacer(1, 3 * mm),
               Paragraph(f"Amount {'payable ' if old else ''}in words: <b>{amount_in_words(payable)}</b>", s),
               Spacer(1, 10 * mm), sign])
    return buf.getvalue()
