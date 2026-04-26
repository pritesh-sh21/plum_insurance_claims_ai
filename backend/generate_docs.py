"""
Mock document generator for Plum Claims System.
Generates realistic Indian medical documents using fpdf2 and Pillow.

Documents generated:
  Clean PDFs (for happy path and policy rejection demos):
    1. prescription_rajesh_kumar.pdf       - TC004 / TC010
    2. hospital_bill_city_clinic.pdf       - TC004
    3. hospital_bill_apollo.pdf            - TC010 network hospital
    4. prescription_vikram_joshi.pdf       - TC005 diabetes waiting period
    5. prescription_mri_suresh_patil.pdf   - TC007 MRI no pre-auth
    6. lab_report_mri.pdf                  - TC007
    7. hospital_bill_mri.pdf               - TC007
    8. dental_bill_smile_clinic.pdf        - TC006 partial approval
    9. prescription_bariatric.pdf          - TC012 excluded treatment
    10. hospital_bill_bariatric.pdf        - TC012

  Demo / edge case documents:
    11. prescription_wrong_second.pdf      - TC001 wrong doc (used as substitute for bill)
    12. blurry_pharmacy_bill.jpg           - TC002 unreadable (Pillow + GaussianBlur)
    13. prescription_rajesh_for_tc003.pdf  - TC003 patient A
    14. hospital_bill_arjun_mehta.pdf      - TC003 patient B (mismatch)
"""

from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

OUT = os.path.join(os.path.dirname(__file__), "sample_docs")
os.makedirs(OUT, exist_ok=True)


# ── PDF helpers ───────────────────────────────────────────────────────────────

def new_pdf() -> FPDF:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15)
    return pdf


def header_box(pdf: FPDF, lines: list[str], fill: tuple = (240, 248, 255)):
    pdf.set_fill_color(*fill)
    pdf.set_draw_color(100, 100, 180)
    pdf.set_line_width(0.5)
    pdf.rect(15, 15, 180, len(lines) * 7 + 6, style="FD")
    pdf.set_xy(18, 18)
    for i, line in enumerate(lines):
        if i == 0:
            pdf.set_font("Helvetica", "B", 11)
        else:
            pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(18, 18 + i * 7)
        pdf.cell(174, 6, line, ln=True)


def section_box(pdf: FPDF, y: float, lines: list[str], fill: tuple = (255, 255, 255)):
    h = len(lines) * 7 + 6
    pdf.set_fill_color(*fill)
    pdf.set_draw_color(180, 180, 180)
    pdf.set_line_width(0.3)
    pdf.rect(15, y, 180, h, style="FD")
    for i, line in enumerate(lines):
        bold = i == 0
        pdf.set_font("Helvetica", "B" if bold else "", 9)
        pdf.set_xy(18, y + 3 + i * 7)
        pdf.cell(174, 6, line, ln=True)
    return y + h + 3


def divider(pdf: FPDF, y: float) -> float:
    pdf.set_draw_color(150, 150, 200)
    pdf.set_line_width(0.3)
    pdf.line(15, y, 195, y)
    return y + 3


def stamp_box(pdf: FPDF, y: float, text: str):
    """Simulate a rubber stamp."""
    pdf.set_draw_color(180, 60, 60)
    pdf.set_line_width(0.8)
    pdf.rect(130, y, 60, 14, style="D")
    pdf.set_font("Helvetica", "BI", 8)
    pdf.set_text_color(180, 60, 60)
    pdf.set_xy(131, y + 4)
    pdf.cell(58, 6, text, align="C")
    pdf.set_text_color(0, 0, 0)


# ── 1. Prescription - Rajesh Kumar (TC004 / TC010) ────────────────────────────

def make_prescription_rajesh():
    pdf = new_pdf()
    header_box(pdf, [
        "Dr. Arun Sharma, MBBS, MD (Internal Medicine)",
        "Reg. No: KA/45678/2015",
        "City Medical Centre, 12 MG Road, Bengaluru - 560001",
        "Ph: +91-80-41234567",
    ])
    y = 50
    y = section_box(pdf, y, [
        "Patient: Rajesh Kumar                    Date: 01-Nov-2024",
        "Age: 39 years    Gender: Male",
        "Chief Complaint: Fever since 3 days, body ache",
    ], fill=(255, 252, 240))

    y = divider(pdf, y)
    y = section_box(pdf, y, [
        "Diagnosis: Viral Fever",
        "",
        "Rx:",
        "  1. Tab Paracetamol 650mg  -  1-1-1 x 5 days",
        "  2. Tab Vitamin C 500mg    -  0-0-1 x 7 days",
        "",
        "Investigations: CBC, Dengue NS1 Antigen",
        "Follow-up: After 5 days if no improvement",
    ])

    stamp_box(pdf, y + 5, "Reg. KA/45678/2015")
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_xy(18, y + 5)
    pdf.cell(100, 14, "Doctor's Signature: _______________")

    pdf.output(f"{OUT}/prescription_rajesh_kumar.pdf")
    print("  created: prescription_rajesh_kumar.pdf")


# ── 2. Hospital Bill - City Clinic (TC004) ────────────────────────────────────

def make_hospital_bill_city_clinic():
    pdf = new_pdf()
    header_box(pdf, [
        "CITY MEDICAL CENTRE",
        "12 MG Road, Bengaluru - 560001  |  GSTIN: 29AABCC1234D1Z5",
        "Ph: 080-41234567  |  Email: citymedical@clinic.in",
    ], fill=(240, 255, 240))

    y = 44
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(15, y)
    pdf.cell(180, 8, "BILL / RECEIPT", align="C", ln=True)
    y += 10

    y = section_box(pdf, y, [
        "Bill No: CMC/2024/08321          Date: 01-Nov-2024",
        "Patient Name: Rajesh Kumar       Age/Gender: 39 / Male",
        "Referring Doctor: Dr. Arun Sharma",
    ], fill=(245, 255, 245))

    y = divider(pdf, y)

    # Table header
    pdf.set_fill_color(200, 230, 200)
    pdf.set_draw_color(100, 150, 100)
    pdf.rect(15, y, 180, 8, style="FD")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(18, y + 1)
    pdf.cell(100, 6, "DESCRIPTION")
    pdf.cell(20, 6, "QTY", align="C")
    pdf.cell(30, 6, "RATE", align="R")
    pdf.cell(27, 6, "AMOUNT", align="R")
    y += 10

    items = [
        ("Consultation Fee (OPD)", "1", "1,000.00", "1,000.00"),
        ("CBC (Complete Blood Count)", "1", "200.00", "200.00"),
        ("Dengue NS1 Antigen Test", "1", "300.00", "300.00"),
    ]
    for desc, qty, rate, amt in items:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(18, y)
        pdf.cell(100, 7, desc)
        pdf.cell(20, 7, qty, align="C")
        pdf.cell(30, 7, rate, align="R")
        pdf.cell(27, 7, amt, align="R")
        y += 7

    y = divider(pdf, y + 2)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(18, y)
    pdf.cell(150, 7, "Subtotal:", align="R")
    pdf.cell(27, 7, "1,500.00", align="R")
    y += 7
    pdf.set_xy(18, y)
    pdf.cell(150, 7, "GST (0% on medical services):", align="R")
    pdf.cell(27, 7, "0.00", align="R")
    y += 7
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_xy(18, y)
    pdf.cell(150, 8, "Total Amount:", align="R")
    pdf.cell(27, 8, "Rs. 1,500.00", align="R")
    y += 12

    pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(18, y)
    pdf.cell(180, 6, "Payment Mode: Cash / UPI / Card")
    stamp_box(pdf, y + 8, "CASHIER STAMP")

    pdf.output(f"{OUT}/hospital_bill_city_clinic.pdf")
    print("  created: hospital_bill_city_clinic.pdf")


# ── 3. Hospital Bill - Apollo Hospitals (TC010) ───────────────────────────────

def make_hospital_bill_apollo():
    pdf = new_pdf()
    header_box(pdf, [
        "APOLLO HOSPITALS",
        "154/11 Bannerghatta Road, Bengaluru - 560076",
        "Ph: 080-26304050  |  GSTIN: 29AABCA1234E1Z3",
    ], fill=(230, 240, 255))

    y = 44
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(15, y)
    pdf.cell(180, 8, "OUTPATIENT BILL", align="C", ln=True)
    y += 10

    y = section_box(pdf, y, [
        "Bill No: APL/2024/11032          Date: 03-Nov-2024",
        "Patient Name: Deepak Shah        Age/Gender: 44 / Male",
        "Referring Doctor: Dr. S. Iyer    Reg: TN/56789/2013",
    ], fill=(240, 245, 255))

    y = divider(pdf, y)

    pdf.set_fill_color(200, 215, 240)
    pdf.rect(15, y, 180, 8, style="FD")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(18, y + 1)
    pdf.cell(110, 6, "DESCRIPTION")
    pdf.cell(40, 6, "RATE", align="R")
    pdf.cell(27, 6, "AMOUNT", align="R")
    y += 10

    items = [
        ("Consultation Fee (OPD)", "1,500.00", "1,500.00"),
        ("Medicines (Amoxicillin 500mg x10, Salbutamol Inhaler)", "3,000.00", "3,000.00"),
    ]
    for desc, rate, amt in items:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(18, y)
        pdf.cell(110, 7, desc)
        pdf.cell(40, 7, rate, align="R")
        pdf.cell(27, 7, amt, align="R")
        y += 7

    y = divider(pdf, y + 2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_xy(18, y)
    pdf.cell(150, 8, "Total Amount:", align="R")
    pdf.cell(27, 8, "Rs. 4,500.00", align="R")
    y += 12

    pdf.set_font("Helvetica", "I", 8)
    pdf.set_xy(18, y)
    pdf.cell(180, 6, "Apollo Hospitals is a network hospital under your Plum Health Insurance policy.")
    stamp_box(pdf, y + 8, "APOLLO NETWORK")

    pdf.output(f"{OUT}/hospital_bill_apollo.pdf")
    print("  created: hospital_bill_apollo.pdf")


# ── 4. Prescription - Vikram Joshi / Diabetes (TC005) ────────────────────────

def make_prescription_vikram():
    pdf = new_pdf()
    header_box(pdf, [
        "Dr. Sunil Mehta, MBBS, MD (General Medicine)",
        "Reg. No: GJ/56789/2014",
        "Mehta Clinic, Sarkhej Road, Ahmedabad - 380015",
        "Ph: +91-79-26587412",
    ])
    y = 50
    y = section_box(pdf, y, [
        "Patient: Vikram Joshi                    Date: 15-Oct-2024",
        "Age: 45 years    Gender: Male",
        "Chief Complaint: Increased thirst, frequent urination, fatigue",
    ], fill=(255, 252, 240))
    y = divider(pdf, y)
    y = section_box(pdf, y, [
        "Diagnosis: Type 2 Diabetes Mellitus (T2DM)",
        "           HbA1c: 8.2%  FBS: 186 mg/dL",
        "",
        "Rx:",
        "  1. Tab Metformin 500mg   -  1-0-1 x 30 days",
        "  2. Tab Glimepiride 1mg   -  1-0-0 x 30 days",
        "  3. Tab Vitamin B12 500mcg - 0-0-1 x 30 days",
        "",
        "Investigations: HbA1c, FBS, PPBS, Kidney function test",
        "Diet: Low carbohydrate, avoid sugar",
        "Follow-up: After 1 month",
    ])
    stamp_box(pdf, y + 5, "Reg. GJ/56789/2014")
    pdf.output(f"{OUT}/prescription_vikram_joshi.pdf")
    print("  created: prescription_vikram_joshi.pdf")


# ── 5. Prescription - MRI / Suresh Patil (TC007) ─────────────────────────────

def make_prescription_mri():
    pdf = new_pdf()
    header_box(pdf, [
        "Dr. Venkat Rao, MBBS, MS (Orthopaedics)",
        "Reg. No: AP/67890/2017",
        "Spine & Joint Care Centre, Hyderabad - 500034",
        "Ph: +91-40-23456789",
    ])
    y = 50
    y = section_box(pdf, y, [
        "Patient: Suresh Patil                    Date: 02-Nov-2024",
        "Age: 49 years    Gender: Male",
        "Chief Complaint: Lower back pain radiating to left leg, 3 weeks",
    ], fill=(255, 252, 240))
    y = divider(pdf, y)
    y = section_box(pdf, y, [
        "Diagnosis: Suspected Lumbar Disc Herniation (L4-L5)",
        "",
        "Rx:",
        "  1. Tab Diclofenac 50mg   -  1-0-1 x 5 days (after food)",
        "  2. Tab Pantoprazole 40mg -  1-0-0 x 5 days",
        "  3. Physiotherapy: 10 sessions",
        "",
        "Investigations Required:",
        "  - MRI Lumbar Spine (with contrast) - URGENT",
        "",
        "Note: MRI required for surgical planning. Please obtain",
        "      insurance pre-authorization before proceeding.",
    ])
    stamp_box(pdf, y + 5, "Reg. AP/67890/2017")
    pdf.output(f"{OUT}/prescription_mri_suresh_patil.pdf")
    print("  created: prescription_mri_suresh_patil.pdf")


# ── 6. Lab Report - MRI (TC007) ───────────────────────────────────────────────

def make_lab_report_mri():
    pdf = new_pdf()
    header_box(pdf, [
        "PRECISION DIAGNOSTICS PVT LTD",
        "NABL Accredited Lab  |  Lab ID: KA-NABL-1234",
        "45 Jayanagar, Bengaluru  |  Ph: 080-22334455",
    ], fill=(245, 240, 255))
    y = 44
    y = section_box(pdf, y, [
        "Patient: Suresh Patil              Age/Sex: 49 / Male",
        "Ref Doctor: Dr. Venkat Rao         Reg: AP/67890/2017",
        "Sample Date: 02-Nov-2024           Report Date: 02-Nov-2024",
        "Sample ID: PD-2024-28931",
    ], fill=(250, 248, 255))
    y = divider(pdf, y)

    pdf.set_fill_color(220, 210, 245)
    pdf.rect(15, y, 180, 8, style="FD")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(18, y + 1)
    pdf.cell(80, 6, "INVESTIGATION")
    pdf.cell(50, 6, "FINDINGS")
    pdf.cell(47, 6, "REMARKS")
    y += 10

    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(80, 7, "MRI Lumbar Spine")
    pdf.cell(50, 7, "L4-L5 Disc Herniation")
    pdf.cell(47, 7, "Nerve root compression")
    y += 10

    y = section_box(pdf, y, [
        "Impression:",
        "  Moderate posterocentral disc herniation at L4-L5 level with left-sided",
        "  neural foraminal narrowing and compression of the L5 nerve root.",
        "  Clinical correlation advised. Surgical opinion recommended.",
    ])

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(18, y + 5)
    pdf.cell(100, 6, "Dr. Meena Pillai, MD (Radiology)  Reg: KA/89012/2018")
    stamp_box(pdf, y + 5, "NABL ACCREDITED")

    pdf.output(f"{OUT}/lab_report_mri.pdf")
    print("  created: lab_report_mri.pdf")


# ── 7. Hospital Bill - MRI (TC007) ────────────────────────────────────────────

def make_hospital_bill_mri():
    pdf = new_pdf()
    header_box(pdf, [
        "PRECISION DIAGNOSTICS PVT LTD",
        "45 Jayanagar, Bengaluru - 560041",
        "Ph: 080-22334455  |  GSTIN: 29AABCD5678F1Z1",
    ], fill=(245, 240, 255))
    y = 44
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(15, y)
    pdf.cell(180, 8, "DIAGNOSTIC BILL", align="C")
    y += 10

    y = section_box(pdf, y, [
        "Bill No: PD/2024/09341           Date: 02-Nov-2024",
        "Patient Name: Suresh Patil       Age/Gender: 49 / Male",
        "Referring Doctor: Dr. Venkat Rao",
    ])
    y = divider(pdf, y)

    pdf.set_fill_color(220, 210, 245)
    pdf.rect(15, y, 180, 8, style="FD")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(18, y + 1)
    pdf.cell(120, 6, "DESCRIPTION")
    pdf.cell(57, 6, "AMOUNT", align="R")
    y += 10

    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(120, 7, "MRI Lumbar Spine (with contrast)")
    pdf.cell(57, 7, "15,000.00", align="R")
    y += 10

    y = divider(pdf, y)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_xy(18, y)
    pdf.cell(150, 8, "Total Amount:", align="R")
    pdf.cell(27, 8, "Rs. 15,000.00", align="R")

    pdf.output(f"{OUT}/hospital_bill_mri.pdf")
    print("  created: hospital_bill_mri.pdf")


# ── 8. Dental Bill - Smile Clinic (TC006) ────────────────────────────────────

def make_dental_bill():
    pdf = new_pdf()
    header_box(pdf, [
        "SMILE DENTAL CLINIC",
        "14 Koramangala 5th Block, Bengaluru - 560095",
        "Ph: 080-25634789  |  Dr. Rekha Nair, BDS, MDS",
    ], fill=(255, 245, 230))
    y = 44
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(15, y)
    pdf.cell(180, 8, "DENTAL TREATMENT BILL", align="C")
    y += 10

    y = section_box(pdf, y, [
        "Bill No: SDC/2024/00521          Date: 15-Oct-2024",
        "Patient Name: Priya Singh        Age/Gender: 34 / Female",
        "Treatment Date: 15-Oct-2024",
    ], fill=(255, 250, 240))
    y = divider(pdf, y)

    pdf.set_fill_color(255, 220, 180)
    pdf.rect(15, y, 180, 8, style="FD")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(18, y + 1)
    pdf.cell(120, 6, "PROCEDURE")
    pdf.cell(57, 6, "AMOUNT", align="R")
    y += 10

    items = [
        ("Root Canal Treatment (Tooth #36)", "8,000.00"),
        ("Teeth Whitening (Cosmetic)", "4,000.00"),
    ]
    for desc, amt in items:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(18, y)
        pdf.cell(120, 7, desc)
        pdf.cell(57, 7, amt, align="R")
        y += 7

    y = divider(pdf, y + 2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_xy(18, y)
    pdf.cell(150, 8, "Total Amount:", align="R")
    pdf.cell(27, 8, "Rs. 12,000.00", align="R")
    y += 12

    pdf.set_font("Helvetica", "I", 8)
    pdf.set_xy(18, y)
    pdf.cell(180, 6, "Note: Cosmetic procedures may not be covered under standard insurance policies.")
    stamp_box(pdf, y + 8, "DENTAL STAMP")

    pdf.output(f"{OUT}/dental_bill_smile_clinic.pdf")
    print("  created: dental_bill_smile_clinic.pdf")


# ── 9. Prescription - Bariatric (TC012) ───────────────────────────────────────

def make_prescription_bariatric():
    pdf = new_pdf()
    header_box(pdf, [
        "Dr. P. Banerjee, MBBS, MS (General Surgery)",
        "Reg. No: WB/34567/2015",
        "Metro Bariatric Centre, Salt Lake, Kolkata - 700091",
        "Ph: +91-33-23456781",
    ])
    y = 50
    y = section_box(pdf, y, [
        "Patient: Anita Desai                     Date: 18-Oct-2024",
        "Age: 31 years    Gender: Female",
        "Chief Complaint: Weight gain, BMI 37, fatigue, joint pain",
    ], fill=(255, 252, 240))
    y = divider(pdf, y)
    y = section_box(pdf, y, [
        "Diagnosis: Morbid Obesity  (BMI: 37.2 kg/m2)",
        "",
        "Treatment Plan:",
        "  1. Bariatric Consultation - initial assessment",
        "  2. Personalised Diet and Nutrition Program (3 months)",
        "  3. Psychological evaluation",
        "  4. Pre-surgical workup if patient opts for surgery",
        "",
        "Rx:",
        "  1. Tab Multivitamin   -  1-0-0 x 30 days",
        "  2. Tab Vitamin D3 60K -  once weekly x 8 weeks",
    ])
    stamp_box(pdf, y + 5, "Reg. WB/34567/2015")
    pdf.output(f"{OUT}/prescription_bariatric.pdf")
    print("  created: prescription_bariatric.pdf")


# ── 10. Hospital Bill - Bariatric (TC012) ─────────────────────────────────────

def make_hospital_bill_bariatric():
    pdf = new_pdf()
    header_box(pdf, [
        "METRO BARIATRIC CENTRE",
        "Salt Lake Sector V, Kolkata - 700091",
        "Ph: 033-23456781",
    ], fill=(255, 240, 240))
    y = 44
    y = section_box(pdf, y, [
        "Bill No: MBC/2024/00831          Date: 18-Oct-2024",
        "Patient Name: Anita Desai        Age/Gender: 31 / Female",
        "Doctor: Dr. P. Banerjee",
    ])
    y = divider(pdf, y)

    items = [("Bariatric Consultation", "3,000.00"),
             ("Personalised Diet and Nutrition Program", "5,000.00")]
    for desc, amt in items:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(18, y)
        pdf.cell(150, 7, desc)
        pdf.cell(27, 7, amt, align="R")
        y += 7

    y = divider(pdf, y + 2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_xy(18, y)
    pdf.cell(150, 8, "Total Amount:", align="R")
    pdf.cell(27, 8, "Rs. 8,000.00", align="R")

    pdf.output(f"{OUT}/hospital_bill_bariatric.pdf")
    print("  created: hospital_bill_bariatric.pdf")


# ── 11. Wrong doc for TC001 - second prescription submitted instead of bill ───

def make_wrong_doc_prescription():
    pdf = new_pdf()
    header_box(pdf, [
        "Dr. Ramesh Iyer, MBBS",
        "Reg. No: KA/11223/2019",
        "Iyer Clinic, Jayanagar, Bengaluru",
    ])
    y = 50
    y = section_box(pdf, y, [
        "Patient: Rajesh Kumar                    Date: 01-Nov-2024",
        "Age: 39 years    Gender: Male",
    ], fill=(255, 252, 240))
    y = divider(pdf, y)
    y = section_box(pdf, y, [
        "Diagnosis: Viral Fever (second opinion)",
        "",
        "Rx:",
        "  1. Tab Dolo 650mg   -  SOS (if fever > 101F)",
        "  2. ORS Sachets      -  twice daily",
        "  3. Rest and fluids",
    ])
    pdf.output(f"{OUT}/prescription_wrong_second.pdf")
    print("  created: prescription_wrong_second.pdf")


# ── 12. Blurry pharmacy bill - TC002 (Pillow + GaussianBlur) ─────────────────

def make_blurry_pharmacy_bill():
    width, height = 800, 600
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    def txt(x, y, text, size=16, bold=False):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                                      if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except Exception:
            font = ImageFont.load_default()
        draw.text((x, y), text, fill=(0, 0, 0), font=font)

    # Draw bill content
    txt(50, 30, "HEALTH FIRST PHARMACY", size=20, bold=True)
    txt(50, 58, "Drug Lic. No: KA-BLR-2024-5521", size=14)
    txt(50, 78, "22 Brigade Road, Bengaluru - 560001", size=14)
    draw.line([(40, 100), (760, 100)], fill=(0, 0, 0), width=2)

    txt(50, 110, "Bill No: HFP-24-09821     Date: 25-Oct-2024", size=14)
    txt(50, 132, "Patient: Sneha Reddy      Dr: Dr. K. Sharma", size=14)
    draw.line([(40, 155), (760, 155)], fill=(0, 0, 0), width=1)

    txt(50, 165, "MEDICINE", size=13, bold=True)
    txt(300, 165, "QTY", size=13, bold=True)
    txt(420, 165, "MRP", size=13, bold=True)
    txt(560, 165, "AMOUNT", size=13, bold=True)
    draw.line([(40, 185), (760, 185)], fill=(150, 150, 150), width=1)

    items = [
        ("Azithromycin 500mg", "3", "45.00", "135.00"),
        ("Pantoprazole 40mg", "5", "12.00", "60.00"),
        ("Cetirizine 10mg", "10", "3.50", "35.00"),
    ]
    for i, (med, qty, mrp, amt) in enumerate(items):
        y = 195 + i * 30
        txt(50, y, med, size=13)
        txt(300, y, qty, size=13)
        txt(420, y, mrp, size=13)
        txt(560, y, amt, size=13)

    draw.line([(40, 290), (760, 290)], fill=(0, 0, 0), width=1)
    txt(420, 300, "Net Amount:", size=14, bold=True)
    txt(560, 300, "Rs. 230.00", size=14, bold=True)

    # Simulate phone photo: slight rotation + blur + brightness variation
    img = img.rotate(2, fillcolor=(255, 255, 255))
    img = img.filter(ImageFilter.GaussianBlur(radius=3))

    # Add noise / shadow patches to simulate bad lighting
    noise_layer = Image.new("RGB", (width, height), (200, 200, 180))
    img = Image.blend(img, noise_layer, alpha=0.25)

    # Extra heavy blur on bottom half (common with phone photos)
    top = img.crop((0, 0, width, height // 2))
    bottom = img.crop((0, height // 2, width, height))
    bottom = bottom.filter(ImageFilter.GaussianBlur(radius=5))
    result = Image.new("RGB", (width, height))
    result.paste(top, (0, 0))
    result.paste(bottom, (0, height // 2))

    result.save(f"{OUT}/blurry_pharmacy_bill.jpg", quality=60)
    print("  created: blurry_pharmacy_bill.jpg")


# ── 13 & 14. TC003 patient mismatch docs ─────────────────────────────────────

def make_tc003_docs():
    # Prescription - Rajesh Kumar
    pdf = new_pdf()
    header_box(pdf, [
        "Dr. Arun Sharma, MBBS, MD",
        "Reg. No: KA/45678/2015",
        "City Medical Centre, Bengaluru",
    ])
    y = 50
    y = section_box(pdf, y, [
        "Patient: Rajesh Kumar                    Date: 01-Nov-2024",
        "Age: 39 years    Gender: Male",
    ], fill=(255, 252, 240))
    y = divider(pdf, y)
    section_box(pdf, y, [
        "Diagnosis: Viral Fever",
        "Rx: Tab Paracetamol 650mg - 1-1-1 x 5 days",
    ])
    pdf.output(f"{OUT}/prescription_rajesh_tc003.pdf")
    print("  created: prescription_rajesh_tc003.pdf")

    # Hospital bill - Arjun Mehta (wrong patient - mismatch)
    pdf2 = new_pdf()
    header_box(pdf2, [
        "CITY MEDICAL CENTRE",
        "12 MG Road, Bengaluru - 560001",
    ], fill=(240, 255, 240))
    y = 44
    y = section_box(pdf2, y, [
        "Bill No: CMC/2024/08322          Date: 01-Nov-2024",
        "Patient Name: Arjun Mehta        Age/Gender: 28 / Male",
        "Referring Doctor: Dr. Arun Sharma",
    ])
    y = divider(pdf2, y)
    pdf2.set_font("Helvetica", "", 9)
    pdf2.set_xy(18, y)
    pdf2.cell(150, 7, "Consultation Fee")
    pdf2.cell(27, 7, "1,000.00", align="R")
    y += 10
    pdf2.set_font("Helvetica", "B", 10)
    pdf2.set_xy(18, y)
    pdf2.cell(150, 8, "Total:", align="R")
    pdf2.cell(27, 8, "Rs. 1,000.00", align="R")
    pdf2.output(f"{OUT}/hospital_bill_arjun_mehta.pdf")
    print("  created: hospital_bill_arjun_mehta.pdf")


# ── Run all ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating mock documents...")
    make_prescription_rajesh()
    make_hospital_bill_city_clinic()
    make_hospital_bill_apollo()
    make_prescription_vikram()
    make_prescription_mri()
    make_lab_report_mri()
    make_hospital_bill_mri()
    make_dental_bill()
    make_prescription_bariatric()
    make_hospital_bill_bariatric()
    make_wrong_doc_prescription()
    make_blurry_pharmacy_bill()
    make_tc003_docs()
    print(f"\nDone. {len(list(__import__('os').scandir(OUT)))-1} files in sample_docs/")
