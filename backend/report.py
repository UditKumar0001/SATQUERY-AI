# backend/report.py
import json
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable


def generate_pdf_report(query_id: int, query_data: dict, out_path: str) -> str:
    """Generate a clean, professional PDF execution audit and analysis report using ReportLab."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    doc = SimpleDocTemplate(
        out_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1e3a8a"),
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=14
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=12,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155")
    )
    code_style = ParagraphStyle(
        "CodeTextCustom",
        parent=styles["Code"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0f172a")
    )

    story = []

    # 1. Header & Title
    story.append(Paragraph("SatQuery AI — Execution Audit Report", title_style))
    story.append(Paragraph(f"Autonomous Multi-Modal Earth Observation Query & Audit Record | Query ID #{query_id}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#cbd5e1"), spaceAfter=12))

    # 2. Key Metadata Summary Table
    trace = query_data.get("trace") or {}
    created_at = query_data.get("created_at") or datetime.utcnow().isoformat()

    summary_table_data = [
        [Paragraph("<b>Selected Task</b>", body_style), Paragraph(str(query_data.get("selected_task")), body_style),
         Paragraph("<b>Model Dispatched</b>", body_style), Paragraph(str(query_data.get("model_used")), body_style)],
        [Paragraph("<b>Router Confidence</b>", body_style), Paragraph(f"{float(query_data.get('router_confidence') or 0.0):.2%}", body_style),
         Paragraph("<b>Output Confidence</b>", body_style), Paragraph(f"{float(query_data.get('output_confidence') or 0.0):.2%}", body_style)],
        [Paragraph("<b>Validation Status</b>", body_style), Paragraph(str(query_data.get("validation_msg")), body_style),
         Paragraph("<b>Execution Time</b>", body_style), Paragraph(str(created_at[:19]).replace("T", " "), body_style)],
    ]
    t = Table(summary_table_data, colWidths=[120, 150, 120, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    # 3. User Query Prompt
    story.append(Paragraph("User Prompt / Instruction", section_heading))
    story.append(Paragraph(query_data.get("query_text", "N/A"), body_style))
    story.append(Spacer(1, 10))

    # 4. Inferred Results & Output
    story.append(Paragraph("Model Inference Output", section_heading))
    result = query_data.get("result") or {}
    result_text = result.get("text") or trace.get("output_summary") or "No textual result recorded."
    story.append(Paragraph(result_text.replace("\n", "<br/>"), body_style))
    story.append(Spacer(1, 10))

    # 5. Input Imagery Manifest Table
    story.append(Paragraph("Ingested Imagery Manifest", section_heading))
    images = query_data.get("images") or []
    if images:
        img_table_data = [["#", "File Path", "Modality", "Format", "Timestamp / Tag"]]
        for idx, img in enumerate(images, 1):
            fp = os.path.basename(img.get("filepath", "")) or img.get("filepath", "")
            img_table_data.append([
                str(idx),
                str(fp),
                str(img.get("modality", "")),
                str(img.get("format", "")),
                str(img.get("timestamp_tag") or "N/A")
            ])
        img_table = Table(img_table_data, colWidths=[24, 230, 90, 80, 116])
        img_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(img_table)
    else:
        story.append(Paragraph("No input imagery registered.", body_style))

    story.append(Spacer(1, 12))

    # 6. Raw Execution Trace Snapshot
    story.append(Paragraph("Auditable Execution Trace (JSON Snapshot)", section_heading))
    trace_json_str = json.dumps(trace, indent=2)
    story.append(Paragraph(f"<font name='Courier'>{trace_json_str.replace(' ', '&nbsp;').replace(chr(10), '<br/>')}</font>", code_style))

    doc.build(story)
    return out_path
