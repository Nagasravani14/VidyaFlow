"""
Generates an official-style proof-of-concept PDF for Telangana SCERT Class 6 Mathematics:
Chapter 1: "Knowing Our Numbers".
Includes authentic curriculum sections, page numbers, place value systems, Roman numerals,
worked examples, and exercises for testing textbook ingestion and passage retrieval.
"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_scert_class6_math_ch1(output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1e3a8a"),
        spaceAfter=12,
    )
    h1_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1e40af"),
        spaceBefore=12,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#1f2937"),
        spaceAfter=8,
    )
    example_style = ParagraphStyle(
        "ExampleBox",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#065f46"),
        backColor=colors.HexColor("#ecfdf5"),
        spaceBefore=6,
        spaceAfter=8,
    )

    story = []

    # --- PAGE 1: Chapter Header & Introduction ---
    story.append(Paragraph("STATE COUNCIL OF EDUCATIONAL RESEARCH &amp; TRAINING (SCERT), TELANGANA", styles["Normal"]))
    story.append(Paragraph("MATHEMATICS — CLASS VI (SEMESTER 1)", styles["Normal"]))
    story.append(Spacer(1, 15))
    story.append(Paragraph("CHAPTER 1: KNOWING OUR NUMBERS", title_style))
    story.append(Paragraph("<b>1.1 Introduction: Comparing Numbers</b>", h1_style))
    story.append(
        Paragraph(
            "Numbers play a vital role in our daily lives. We use numbers to count objects, measure distances, "
            "calculate expenses, and compare quantities. In earlier classes, we learned about natural numbers "
            "and whole numbers. In this chapter, we will learn how to read, write, compare, and operate on large numbers "
            "up to 8 and 9 digits.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "<b>Comparing Two Numbers:</b><br/>"
            "Rule 1: If two numbers have an unequal number of digits, the number with more digits is greater.<br/>"
            "Example: 9,210 has 4 digits while 856 has 3 digits. Therefore, 9,210 &gt; 856.<br/>"
            "Rule 2: If two numbers have the same number of digits, compare the leftmost digits. If they are equal, "
            "compare the second digits from the left, and so forth.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "<b>Example 1:</b> Which is greater: 67,542 or 67,821?<br/>"
            "Solution: Both have 5 digits. The ten-thousands digit (6) and thousands digit (7) are identical. "
            "Comparing hundreds: 8 &gt; 5. Thus, 67,821 &gt; 67,542.",
            example_style,
        )
    )

    story.append(PageBreak())

    # --- PAGE 2: Place Value in Indian vs International Systems ---
    story.append(Paragraph("CHAPTER 1: KNOWING OUR NUMBERS (Contd.)", styles["Normal"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>1.2 The Indian System of Numeration</b>", h1_style))
    story.append(
        Paragraph(
            "In the Indian System of Numeration, place values are grouped into periods: "
            "<b>Units period</b> (Ones, Tens, Hundreds), <b>Thousands period</b> (Thousands, Ten Thousands), "
            "<b>Lakhs period</b> (Lakhs, Ten Lakhs), and <b>Crores period</b> (Crores, Ten Crores).<br/>"
            "Commas are placed: first after 3 digits from right, then after every 2 digits.<br/>"
            "For instance, 5,08,21,340 is read as: <i>Five crore eight lakh twenty-one thousand three hundred and forty</i>.",
            body_style,
        )
    )

    story.append(Paragraph("<b>1.3 The International System of Numeration</b>", h1_style))
    story.append(
        Paragraph(
            "In the International System of Numeration, place values are grouped in threes: "
            "<b>Units period</b> (Ones, Tens, Hundreds), <b>Thousands period</b> (Thousands, Ten Thousands, Hundred Thousands), "
            "and <b>Millions period</b> (Millions, Ten Millions, Hundred Millions).<br/>"
            "Commas are placed after every 3 digits from the right.<br/>"
            "The same number 50,821,340 is read as: <i>Fifty million eight hundred twenty-one thousand three hundred forty</i>.",
            body_style,
        )
    )

    table_data = [
        ["Value", "Indian System", "International System"],
        ["1,00,000", "1 Lakh", "100 Thousand"],
        ["10,00,000", "10 Lakh (10 Lakhs)", "1 Million"],
        ["1,00,00,000", "1 Crore", "10 Million"],
        ["10,00,00,000", "10 Crores", "100 Million"],
    ]
    t = Table(table_data, colWidths=[120, 160, 160])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e7ff")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(t)

    story.append(PageBreak())

    # --- PAGE 3: Estimation & Rounding Off ---
    story.append(Paragraph("CHAPTER 1: KNOWING OUR NUMBERS (Contd.)", styles["Normal"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>1.4 Estimation and Rounding Off</b>", h1_style))
    story.append(
        Paragraph(
            "Estimation gives a quick, rough value to check the reasonableness of an answer or when exact numbers are not necessary.<br/>"
            "<b>Rounding to nearest Tens:</b> Look at the ones digit. If 0–4, round down. If 5–9, round up.<br/>"
            "Example: 73 rounds to 70; 78 rounds to 80.<br/>"
            "<b>Rounding to nearest Hundreds:</b> Look at tens digit. Example: 428 rounds to 400; 472 rounds to 500.<br/>"
            "<b>Rounding to nearest Thousands:</b> Look at hundreds digit. Example: 7,499 rounds to 7,000; 7,501 rounds to 8,000.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "<b>General Rule for Estimating Products:</b> Round each factor to its greatest place value, then multiply.<br/>"
            "Example: Estimate 578 × 161.<br/>"
            "578 rounds to 600 (nearest hundred). 161 rounds to 200 (nearest hundred).<br/>"
            "Estimated Product = 600 × 200 = 1,20,000.",
            example_style,
        )
    )

    story.append(PageBreak())

    # --- PAGE 4: Roman Numerals & Exercises ---
    story.append(Paragraph("CHAPTER 1: KNOWING OUR NUMBERS (Contd.)", styles["Normal"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>1.5 Roman Numerals</b>", h1_style))
    story.append(
        Paragraph(
            "The Romans used seven basic symbols:<br/>"
            "<b>I = 1, V = 5, X = 10, L = 50, C = 100, D = 500, M = 1000</b>.<br/>"
            "<b>Key Rules:</b><br/>"
            "1. A symbol is not repeated more than three times (I, X, C, M). V, L, D are never repeated.<br/>"
            "2. If a smaller symbol is written to the right of a greater symbol, its value is added (e.g., VI = 5 + 1 = 6; XII = 10 + 2 = 12).<br/>"
            "3. If a smaller symbol is written to the left of a greater symbol, its value is subtracted (e.g., IV = 5 - 1 = 4; IX = 10 - 1 = 9).<br/>"
            "4. The symbols V, L, and D are never written to the left of a symbol of greater value (they are never subtracted).<br/>"
            "5. Symbol I can be subtracted from V and X only. Symbol X can be subtracted from L, M, and C only.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "<b>Example 4:</b> Write 69 and 98 in Roman Numerals.<br/>"
            "Solution: 69 = 60 + 9 = (50 + 10) + 9 = LX + IX = LXIX.<br/>"
            "98 = 90 + 8 = (100 - 10) + 8 = XC + VIII = XCVIII.",
            example_style,
        )
    )

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>EXERCISE 1.1</b>", h1_style))
    story.append(
        Paragraph(
            "1. Fill in the blanks:<br/>"
            "   (a) 1 lakh = _____ ten thousand.<br/>"
            "   (b) 1 million = _____ hundred thousand.<br/>"
            "   (c) 1 crore = _____ ten lakh.<br/>"
            "   (d) 1 crore = _____ million.<br/>"
            "2. Place commas correctly and write numerals: <i>Seventy-three lakh seventy-five thousand three hundred seven</i>.<br/>"
            "3. Write Roman numerals for: (a) 49 (b) 73 (c) 92.<br/>"
            "4. A vessel has 4 litres and 500 ml of curd. In how many glasses, each of 25 ml capacity, can it be filled?",
            body_style,
        )
    )

    doc.build(story)
    print(f"Generated official sample PDF at: {output_path}")


if __name__ == "__main__":
    out_file = os.path.join("storage", "downloads", "ts_scert_class6_math_ch1.pdf")
    generate_scert_class6_math_ch1(out_file)
