from io import BytesIO
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer
)


def format_inline_markdown(text):
    """Convert a small, safe subset of Markdown into ReportLab paragraph markup."""
    text = escape(text)
    text = re.sub(r"`([^`]+)`", r'<font name="Courier" color="#3157d5">\1</font>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    return text


def create_article_pdf(title, date, category, content):
    """Build a downloadable, styled PDF for one published blog article."""
    pdf_buffer = BytesIO()

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="BlogTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=23,
        leading=29,
        textColor=colors.HexColor("#14213d"),
        alignment=TA_LEFT,
        spaceAfter=12
    ))
    styles.add(ParagraphStyle(
        name="BlogMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=14,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=5
    ))
    styles.add(ParagraphStyle(
        name="BlogH1",
        parent=styles["Heading1"],
        fontSize=17,
        leading=22,
        textColor=colors.HexColor("#193858"),
        spaceBefore=15,
        spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        name="BlogH2",
        parent=styles["Heading2"],
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#244a76"),
        spaceBefore=12,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name="BlogBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=16,
        textColor=colors.HexColor("#29384d"),
        spaceAfter=9
    ))
    styles.add(ParagraphStyle(
        name="BlogQuote",
        parent=styles["BodyText"],
        fontName="Helvetica-Oblique",
        fontSize=10,
        leading=16,
        leftIndent=14,
        textColor=colors.HexColor("#52647b"),
        borderColor=colors.HexColor("#9bb5d0"),
        borderWidth=2,
        borderPadding=8,
        spaceBefore=5,
        spaceAfter=10
    ))
    styles.add(ParagraphStyle(
        name="BlogCode",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=8,
        leading=11,
        backColor=colors.HexColor("#f1f5f9"),
        borderPadding=8,
        spaceBefore=5,
        spaceAfter=9
    ))

    def add_page_footer(canvas, document):
        canvas.saveState()
        page_width, _ = A4
        canvas.setStrokeColor(colors.HexColor("#dce3ec"))
        canvas.setLineWidth(0.6)
        canvas.line(20 * mm, 17 * mm, page_width - 20 * mm, 17 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#718096"))
        canvas.drawString(20 * mm, 11 * mm, "My Personal Blog")
        canvas.drawRightString(page_width - 20 * mm, 11 * mm, f"Page {document.page}")
        canvas.restoreState()

    document = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=22 * mm,
        bottomMargin=25 * mm,
        title=title,
        author="My Personal Blog"
    )

    story = [
        Paragraph(escape(title), styles["BlogTitle"]),
        Paragraph(f"<b>Category:</b> {escape(str(category))}", styles["BlogMeta"]),
        Paragraph(f"<b>Published:</b> {escape(str(date))}", styles["BlogMeta"]),
        Spacer(1, 5 * mm),
        HRFlowable(
            width="100%",
            thickness=1,
            color=colors.HexColor("#dce3ec"),
            spaceAfter=7 * mm
        )
    ]

    paragraph_lines = []
    code_lines = []
    in_code_block = False
    first_heading_skipped = False

    def flush_paragraph():
        if paragraph_lines:
            paragraph_text = " ".join(line.strip() for line in paragraph_lines)
            story.append(Paragraph(
                format_inline_markdown(paragraph_text),
                styles["BlogBody"]
            ))
            paragraph_lines.clear()

    for raw_line in content.splitlines():
        line = raw_line.rstrip()

        if line.strip().startswith("```"):
            flush_paragraph()
            if in_code_block:
                story.append(Preformatted("\n".join(code_lines), styles["BlogCode"]))
                code_lines.clear()
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        if not line.strip():
            flush_paragraph()
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading_match:
            flush_paragraph()
            heading_level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()

            if not first_heading_skipped and heading_level == 1 and heading_text.casefold() == title.casefold():
                first_heading_skipped = True
                continue

            heading_style = styles["BlogH1"] if heading_level == 1 else styles["BlogH2"]
            story.append(Paragraph(
                format_inline_markdown(heading_text),
                heading_style
            ))
            continue

        if re.match(r"^\s*([-*_])\1\1+\s*$", line):
            flush_paragraph()
            story.append(HRFlowable(
                width="100%",
                thickness=0.5,
                color=colors.HexColor("#dce3ec"),
                spaceBefore=5,
                spaceAfter=8
            ))
            continue

        if line.startswith(">"):
            flush_paragraph()
            quote_text = line.lstrip("> ").strip()
            story.append(Paragraph(
                format_inline_markdown(quote_text),
                styles["BlogQuote"]
            ))
            continue

        bullet_match = re.match(r"^\s*[-*]\s+(.+)$", line)
        number_match = re.match(r"^\s*(\d+)\.\s+(.+)$", line)

        if bullet_match or number_match:
            flush_paragraph()
            if bullet_match:
                bullet = "•"
                item_text = bullet_match.group(1)
            else:
                bullet = f"{number_match.group(1)}."
                item_text = number_match.group(2)

            story.append(Paragraph(
                format_inline_markdown(item_text),
                styles["BlogBody"],
                bulletText=bullet
            ))
            continue

        paragraph_lines.append(line)

    flush_paragraph()

    if in_code_block and code_lines:
        story.append(Preformatted("\n".join(code_lines), styles["BlogCode"]))

    document.build(
        story,
        onFirstPage=add_page_footer,
        onLaterPages=add_page_footer
    )

    pdf_buffer.seek(0)
    return pdf_buffer
