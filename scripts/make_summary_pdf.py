#!/usr/bin/env python3
"""Build web/public/summary.pdf (one-page printable project summary + QR)."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import qrcode
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'web' / 'public' / 'summary.pdf'
SITE = 'https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/'
DOI = 'https://doi.org/10.5281/zenodo.23286597'
CREDIT = (
    'Project by Surabhi Fadnavis. The code, analysis, text, and video were '
    'produced with AI tools (Cursor).'
)


def draw_wrapped(c, text, x, y, max_w, font='Helvetica', size=10, leading=14, color=None):
    c.setFont(font, size)
    if color is not None:
        c.setFillColor(color)
    line_s = ''
    for w in text.split():
        trial = (line_s + ' ' + w).strip()
        if stringWidth(trial, font, size) <= max_w:
            line_s = trial
        else:
            c.drawString(x, y, line_s)
            y -= leading
            line_s = w
    if line_s:
        c.drawString(x, y, line_s)
        y -= leading
    return y


def main() -> None:
    qr = qrcode.QRCode(version=2, box_size=8, border=2)
    qr.add_data(SITE)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color='#0e0e0e', back_color='white')
    qr_buf = BytesIO()
    qr_img.save(qr_buf, format='PNG')
    qr_buf.seek(0)

    W, H = letter
    c = canvas.Canvas(str(OUT), pagesize=letter)
    teal = HexColor('#297373')
    ink = HexColor('#0e0e0e')
    muted = HexColor('#4a5858')
    line = HexColor('#c5d4d4')

    c.setFillColor(teal)
    c.rect(0, H - 0.55 * inch, W, 0.55 * inch, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(
        W / 2,
        H - 0.34 * inch,
        'RESEARCH DEMO · NOT FOR CLINICAL USE · NEVER USE FOR DIAGNOSIS OR CARE',
    )

    y = H - 1.05 * inch
    c.setFillColor(ink)
    c.setFont('Helvetica-Bold', 18)
    c.drawString(0.75 * inch, y, 'Breast Ultrasound Lesion Segmentation')
    y -= 0.28 * inch
    c.setFont('Helvetica', 11)
    c.setFillColor(muted)
    c.drawString(0.75 * inch, y, 'Surabhi Fadnavis · high-school research project · model v1.0.0')

    y -= 0.35 * inch
    c.setStrokeColor(line)
    c.setLineWidth(1)
    c.line(0.75 * inch, y, W - 0.75 * inch, y)

    y -= 0.4 * inch
    c.setFillColor(ink)
    c.setFont('Helvetica-Bold', 12)
    c.drawString(0.75 * inch, y, 'What this is')
    y -= 0.22 * inch
    y = draw_wrapped(
        c,
        'A browser demo that draws a lump outline on breast ultrasound images and shows a '
        'harmless vs cancerous score. The model runs on your device. Images are not uploaded.',
        0.75 * inch,
        y,
        W - 1.5 * inch,
        color=ink,
    )

    y -= 0.15 * inch
    c.setFont('Helvetica-Bold', 12)
    c.setFillColor(ink)
    c.drawString(0.75 * inch, y, 'Key results (browser model v1.0.0)')
    y -= 0.28 * inch
    rows = [
        ('BUSI held-out test', 'Outline-overlap (Dice) 0.697 · lump-only Dice 0.764 · AUC 0.931'),
        ('BUS-BRA (outside)', 'Dice 0.714 · AUC 0.638'),
        ('BrEaST (outside)', 'Dice 0.627 · AUC 0.721'),
        (
            'BUS-UCLM (outside)',
            '640 images / 38 patients · Dice 0.386 · lump-only 0.679 · AUC 0.780',
        ),
    ]
    for label, val in rows:
        c.setFillColor(teal)
        c.setFont('Helvetica-Bold', 10)
        c.drawString(0.75 * inch, y, label)
        y -= 0.18 * inch
        y = draw_wrapped(c, val, 0.9 * inch, y, W - 2.8 * inch, color=ink)
        y -= 0.08 * inch

    y -= 0.1 * inch
    c.setFont('Helvetica-Bold', 12)
    c.setFillColor(ink)
    c.drawString(0.75 * inch, y, 'Limits')
    y -= 0.22 * inch
    y = draw_wrapped(
        c,
        'Research only. Not a medical device. Scores are not a diagnosis. Outside datasets score '
        'lower. Normal (no lump) scans can still get false outlines. Do not use for care decisions.',
        0.75 * inch,
        y,
        W - 2.8 * inch,
        color=ink,
    )

    qr_x = W - 2.35 * inch
    qr_y = 2.6 * inch
    c.drawImage(ImageReader(qr_buf), qr_x, qr_y, width=1.45 * inch, height=1.45 * inch, mask='auto')
    c.setFont('Helvetica', 8)
    c.setFillColor(muted)
    c.drawCentredString(qr_x + 0.725 * inch, qr_y - 0.18 * inch, 'Live demo')
    c.setFont('Helvetica', 7)
    c.drawCentredString(qr_x + 0.725 * inch, qr_y - 0.32 * inch, 'Scan to open the site')

    y = min(y, qr_y - 0.55 * inch)
    y -= 0.15 * inch
    c.setStrokeColor(line)
    c.line(0.75 * inch, y, W - 0.75 * inch, y)
    y -= 0.3 * inch

    c.setFont('Helvetica-Bold', 11)
    c.setFillColor(ink)
    c.drawString(0.75 * inch, y, 'Credit')
    y -= 0.2 * inch
    y = draw_wrapped(c, CREDIT, 0.75 * inch, y, W - 1.5 * inch, color=ink)

    y -= 0.12 * inch
    c.setFont('Helvetica-Bold', 11)
    c.drawString(0.75 * inch, y, 'Cite / DOI')
    y -= 0.2 * inch
    y = draw_wrapped(
        c,
        f'Fadnavis, S. (2026). Breast ultrasound lesion segmentation research demo '
        f'(Version 1.0.0). Zenodo. {DOI}',
        0.75 * inch,
        y,
        W - 1.5 * inch,
        color=ink,
    )

    y -= 0.15 * inch
    c.setFont('Helvetica-Bold', 11)
    c.drawString(0.75 * inch, y, 'Disclaimer')
    y -= 0.2 * inch
    y = draw_wrapped(
        c,
        'This project is a student research demo. It is not for clinical use, screening, '
        'diagnosis, or any care decision.',
        0.75 * inch,
        y,
        W - 1.5 * inch,
        color=ink,
    )

    c.setFillColor(muted)
    c.setFont('Helvetica', 8)
    c.drawString(0.75 * inch, 0.55 * inch, SITE)
    c.drawRightString(W - 0.75 * inch, 0.55 * inch, 'One-page summary · free tools only')
    c.showPage()
    c.save()
    print(f'Wrote {OUT} ({OUT.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
