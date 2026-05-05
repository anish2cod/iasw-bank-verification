#!/usr/bin/env python3
"""Generate mock marriage certificate PDFs for testing."""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("Warning: reportlab not installed. Install with: pip install reportlab")


def generate_marriage_certificate(
    bride_name: str = "Priya Sharma",
    groom_name: str = "Rahul Mehta",
    married_name: str = "Priya Mehta",
    marriage_date: str = "15th January 2024",
    registration_number: str = "MC-2024-001234",
    output_path: str = None,
) -> str:
    """
    Generate a mock marriage certificate PDF.

    Args:
        bride_name: Name of the bride before marriage
        groom_name: Name of the groom
        married_name: Bride's new married name
        marriage_date: Date of marriage
        registration_number: Certificate registration number
        output_path: Path to save the PDF (optional)

    Returns:
        Path to the generated PDF
    """
    if not REPORTLAB_AVAILABLE:
        # Create a simple text file instead
        if output_path is None:
            output_dir = Path(__file__).parent.parent.parent / "data" / "uploads"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"marriage_certificate_{registration_number}.txt"

        content = f"""
CERTIFICATE OF MARRIAGE
Registration Number: {registration_number}

This is to certify that the following persons were united in marriage:

Bride: {bride_name}
Groom: {groom_name}

Date of Marriage: {marriage_date}
Place of Marriage: Mumbai, Maharashtra

The bride will henceforth be known as:
Married Name: {married_name}

Witnessed and registered under the Hindu Marriage Act, 1955.

Registrar of Marriages
Mumbai District
"""
        with open(output_path, "w") as f:
            f.write(content)

        print(f"Text certificate generated: {output_path}")
        return str(output_path)

    # Generate PDF
    if output_path is None:
        output_dir = Path(__file__).parent.parent.parent / "data" / "uploads"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"marriage_certificate_{registration_number}.pdf"

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=1*inch,
        leftMargin=1*inch,
        topMargin=1*inch,
        bottomMargin=1*inch,
    )

    # Styles
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=24,
        alignment=TA_CENTER,
        spaceAfter=30,
        textColor=colors.darkblue,
    )

    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER,
        spaceAfter=20,
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=11,
        alignment=TA_LEFT,
        spaceAfter=12,
        leading=16,
    )

    label_style = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_LEFT,
        textColor=colors.grey,
    )

    value_style = ParagraphStyle(
        'Value',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_LEFT,
        fontName='Helvetica-Bold',
    )

    # Build document
    story = []

    # Header
    story.append(Paragraph("GOVERNMENT OF MAHARASHTRA", subtitle_style))
    story.append(Paragraph("OFFICE OF THE REGISTRAR OF MARRIAGES", subtitle_style))
    story.append(Spacer(1, 20))

    # Title
    story.append(Paragraph("CERTIFICATE OF MARRIAGE", title_style))

    # Registration number
    story.append(Paragraph(f"Registration Number: {registration_number}", subtitle_style))
    story.append(Spacer(1, 30))

    # Preamble
    story.append(Paragraph(
        "This is to certify that the following persons were lawfully united in marriage "
        "in accordance with the provisions of the Hindu Marriage Act, 1955:",
        body_style
    ))
    story.append(Spacer(1, 20))

    # Details table
    details_data = [
        ["Bride:", bride_name],
        ["Groom:", groom_name],
        ["Date of Marriage:", marriage_date],
        ["Place of Marriage:", "Mumbai, Maharashtra, India"],
    ]

    details_table = Table(details_data, colWidths=[2*inch, 4*inch])
    details_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 30))

    # New name section
    story.append(Paragraph(
        "Pursuant to this marriage, the bride has chosen to adopt the following name:",
        body_style
    ))
    story.append(Spacer(1, 10))

    name_data = [["Married Name:", married_name]]
    name_table = Table(name_data, colWidths=[2*inch, 4*inch])
    name_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BOX', (1, 0), (1, 0), 1, colors.black),
        ('BACKGROUND', (1, 0), (1, 0), colors.lightyellow),
    ]))
    story.append(name_table)
    story.append(Spacer(1, 40))

    # Footer
    story.append(Paragraph(
        "This certificate is issued under the authority of the Registrar of Marriages, "
        "Mumbai District, and is valid for all legal purposes.",
        body_style
    ))
    story.append(Spacer(1, 30))

    # Signature section
    sig_data = [
        ["", ""],
        ["_______________________", "_______________________"],
        ["Witness", "Registrar of Marriages"],
        ["", "Mumbai District"],
    ]
    sig_table = Table(sig_data, colWidths=[3*inch, 3*inch])
    sig_table.setStyle(TableStyle([
        ('ALIGNMENT', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 2), (-1, 2), 5),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 20))

    # Date
    story.append(Paragraph(
        f"Date of Issue: {datetime.now().strftime('%d %B %Y')}",
        ParagraphStyle('Date', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10)
    ))

    # Build PDF
    doc.build(story)

    print(f"Marriage certificate generated: {output_path}")
    return str(output_path)


def generate_sample_certificates():
    """Generate sample certificates for testing."""
    output_dir = Path(__file__).parent.parent.parent / "data" / "uploads"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Sample 1: Perfect match for C001
    generate_marriage_certificate(
        bride_name="Priya Sharma",
        groom_name="Rahul Mehta",
        married_name="Priya Mehta",
        marriage_date="15th January 2024",
        registration_number="MC-2024-001234",
        output_path=str(output_dir / "sample_certificate_priya.pdf"),
    )

    # Sample 2: Another test case for C003
    generate_marriage_certificate(
        bride_name="Anita Desai",
        groom_name="Vikash Patel",
        married_name="Anita Patel",
        marriage_date="20th February 2024",
        registration_number="MC-2024-005678",
        output_path=str(output_dir / "sample_certificate_anita.pdf"),
    )

    print("\nSample certificates generated in:", output_dir)


if __name__ == "__main__":
    generate_sample_certificates()
