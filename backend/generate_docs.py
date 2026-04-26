"""
Mock document generator for Plum Claims System.
Generates realistic Indian medical documents using fpdf2 and Pillow.

Run from backend/ directory:
    python generate_docs.py

Documents generated:
  TC001 - Wrong doc demo
    prescription_rajesh_kumar.pdf       EMP001 Rajesh Kumar prescription
    prescription_wrong_second.pdf       Second prescription (wrong doc type for consultation)

  TC002 - Unreadable doc demo
    blurry_pharmacy_bill.jpg            Blurry pharmacy bill (Pillow + aggressive blur)

  TC003 - Patient mismatch demo
    prescription_rajesh_tc003.pdf       Rajesh Kumar prescription
    hospital_bill_arjun_mehta.pdf       Arjun Mehta bill (different patient)

  TC004 - Clean consultation approval
    hospital_bill_city_clinic.pdf       Rajesh Kumar bill at City Clinic

  TC005 - Diabetes waiting period
    prescription_vikram_joshi.pdf       Vikram Joshi - T2DM diagnosis
    hospital_bill_vikram_joshi.pdf      Vikram Joshi bill at Mehta Clinic

  TC006 - Dental partial approval
    dental_bill_smile_clinic.pdf        Priya Singh - root canal + whitening

  TC007 - MRI no pre-auth
    prescription_mri_suresh_patil.pdf   Suresh Patil - MRI ordered
    lab_report_mri.pdf                  MRI findings report
    hospital_bill_mri.pdf               MRI diagnostic bill

  TC008 - Per-claim limit exceeded
    prescription_amit_verma.pdf         Amit Verma - gastroenteritis
    hospital_bill_amit_verma.pdf        Amit Verma bill Rs.7500

  TC009 - Fraud (tested via Swagger/JSON - no PDFs needed)

  TC010 - Apollo network hospital
    prescription_deepak_shah.pdf        Deepak Shah - acute bronchitis
    hospital_bill_apollo.pdf            Apollo Hospitals bill Rs.4500

  TC011 - Graceful degradation (tested via Swagger/JSON - no PDFs needed)

  TC012 - Excluded treatment
    prescription_anita_desai.pdf        Anita Desai - morbid obesity
    hospital_bill_anita_desai.pdf       Bariatric centre bill Rs.8000

  TC003 mismatch patient:
    hospital_bill_arjun_mehta.pdf       Arjun Mehta (not a member - for mismatch demo)
"""

import os
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = os.path.join(os.path.dirname(__file__), "sample_docs")
os.makedirs(OUT, exist_ok=True)


# ── PDF helpers ───────────────────────────────────────────────────────────────

def new_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15)
    return pdf


def rx_header(pdf, doctor, reg, clinic, phone=""):
    pdf.set_fill_color(240, 248, 255)
    pdf.set_draw_color(100, 100, 180)
    pdf.set_line_width(0.5)
    h = 30 if phone else 24
    pdf.rect(15, 15, 180, h, style="FD")
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(18, 18)
    pdf.cell(174, 6, doctor, ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, 25)
    pdf.cell(174, 6, f"Reg. No: {reg}", ln=True)
    pdf.set_xy(18, 32)
    pdf.cell(174, 6, clinic, ln=True)
    if phone:
        pdf.set_xy(18, 39)
        pdf.cell(174, 6, f"Ph: {phone}", ln=True)


def bill_header(pdf, clinic, address, gstin="", fill=(240, 255, 240)):
    pdf.set_fill_color(*fill)
    pdf.set_draw_color(100, 100, 180)
    h = 30 if gstin else 24
    pdf.rect(15, 15, 180, h, style="FD")
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(18, 18)
    pdf.cell(174, 6, clinic, ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, 25)
    pdf.cell(174, 6, address, ln=True)
    if gstin:
        pdf.set_xy(18, 32)
        pdf.cell(174, 6, f"GSTIN: {gstin}", ln=True)


def patient_row(pdf, y, name, age_gender, date, bill_no=""):
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    if bill_no:
        pdf.cell(174, 6, f"Bill No: {bill_no}          Date: {date}", ln=True)
        pdf.set_xy(18, y + 7)
        pdf.cell(174, 6, f"Patient Name: {name}     Age/Gender: {age_gender}", ln=True)
    else:
        pdf.cell(174, 6, f"Patient: {name}                     Date: {date}", ln=True)
        pdf.set_xy(18, y + 7)
        pdf.cell(174, 6, f"Age/Gender: {age_gender}", ln=True)


def bill_items(pdf, y, items):
    """Draw line items and return final y."""
    pdf.set_draw_color(180, 180, 180)
    pdf.set_line_width(0.3)
    # header
    pdf.set_fill_color(200, 230, 200)
    pdf.rect(15, y, 180, 8, style="FD")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(18, y + 1)
    pdf.cell(130, 6, "DESCRIPTION")
    pdf.cell(47, 6, "AMOUNT", align="R")
    y += 10
    for desc, amt in items:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(18, y)
        pdf.cell(130, 7, desc)
        pdf.cell(47, 7, f"{amt:,.2f}", align="R")
        y += 7
    return y


def total_row(pdf, y, total):
    pdf.set_draw_color(100, 150, 100)
    pdf.line(15, y, 195, y)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_xy(18, y + 2)
    pdf.cell(150, 8, "Total Amount:", align="R")
    pdf.cell(27, 8, f"Rs. {total:,.2f}", align="R")


def stamp(pdf, y, text, color=(180, 60, 60)):
    pdf.set_draw_color(*color)
    pdf.set_line_width(0.8)
    pdf.rect(130, y, 60, 14, style="D")
    pdf.set_font("Helvetica", "BI", 8)
    pdf.set_text_color(*color)
    pdf.set_xy(131, y + 4)
    pdf.cell(58, 6, text, align="C")
    pdf.set_text_color(0, 0, 0)


# ── TC001 + TC004 — Rajesh Kumar prescription ─────────────────────────────────

def make_prescription_rajesh():
    pdf = new_pdf()
    rx_header(pdf,
        "Dr. Arun Sharma, MBBS, MD (Internal Medicine)",
        "KA/45678/2015",
        "City Medical Centre, 12 MG Road, Bengaluru - 560001",
        "+91-80-41234567"
    )
    y = 52
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Patient: Rajesh Kumar                    Date: 01-Nov-2024", ln=True)
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "Age: 39 years    Gender: Male", ln=True)
    y += 20
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Diagnosis: Viral Fever", ln=True)
    y += 10
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Rx:", ln=True)
    for i, line in enumerate([
        "1. Tab Paracetamol 650mg  -  1-1-1 x 5 days",
        "2. Tab Vitamin C 500mg    -  0-0-1 x 7 days",
    ]):
        pdf.set_xy(18, y + 7 + i * 7)
        pdf.cell(174, 6, f"  {line}", ln=True)
    y += 28
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Investigations: CBC, Dengue NS1 Antigen", ln=True)
    stamp(pdf, y + 10, "Reg. KA/45678/2015")
    pdf.output(f"{OUT}/prescription_rajesh_kumar.pdf")
    print("  created: prescription_rajesh_kumar.pdf")


# ── TC001 — Wrong second doc ──────────────────────────────────────────────────

def make_prescription_wrong_second():
    pdf = new_pdf()
    rx_header(pdf, "Dr. Ramesh Iyer, MBBS", "KA/11223/2019",
              "Iyer Clinic, Jayanagar, Bengaluru")
    y = 46
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Patient: Rajesh Kumar                    Date: 01-Nov-2024", ln=True)
    y += 14
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Diagnosis: Viral Fever (second opinion)", ln=True)
    y += 10
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Rx:", ln=True)
    for i, line in enumerate([
        "1. Tab Dolo 650mg   -  SOS (if fever > 101F)",
        "2. ORS Sachets      -  twice daily",
        "3. Rest and fluids",
    ]):
        pdf.set_xy(18, y + 7 + i * 7)
        pdf.cell(174, 6, f"  {line}", ln=True)
    pdf.output(f"{OUT}/prescription_wrong_second.pdf")
    print("  created: prescription_wrong_second.pdf")


# ── TC002 — Blurry pharmacy bill ──────────────────────────────────────────────

def make_blurry_pharmacy_bill():
    width, height = 800, 600
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    try:
        font_b = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        font   = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except Exception:
        font_b = font = ImageFont.load_default()

    draw.text((50, 30),  "HEALTH FIRST PHARMACY",              fill="black", font=font_b)
    draw.text((50, 58),  "Drug Lic: KA-BLR-2024-5521",        fill="black", font=font)
    draw.text((50, 78),  "22 Brigade Road, Bengaluru - 560001",fill="black", font=font)
    draw.line([(40, 100), (760, 100)], fill="black", width=2)
    draw.text((50, 110), "Bill: HFP-24-09821   Date: 25-Oct-2024", fill="black", font=font)
    draw.text((50, 132), "Patient: Sneha Reddy   Dr: Dr. K. Sharma", fill="black", font=font)
    draw.line([(40, 155), (760, 155)], fill="black", width=1)
    draw.text((50, 165), "Azithromycin 500mg x3   Rs.135",    fill="black", font=font)
    draw.text((50, 195), "Pantoprazole 40mg x5    Rs.60",     fill="black", font=font)
    draw.text((50, 225), "Cetirizine 10mg x10     Rs.35",     fill="black", font=font)
    draw.line([(40, 255), (760, 255)], fill="black", width=1)
    draw.text((50, 265), "Net Amount: Rs. 230.00",            fill="black", font=font_b)

    # Aggressive blur: downscale to tiny then upscale
    tiny   = img.resize((20, 15), Image.LANCZOS)
    blurry = tiny.resize((width, height), Image.NEAREST)
    for _ in range(8):
        blurry = blurry.filter(ImageFilter.GaussianBlur(radius=5))
    noise = Image.new("RGB", (width, height), (160, 160, 140))
    blurry = Image.blend(blurry, noise, alpha=0.5)
    blurry.save(f"{OUT}/blurry_pharmacy_bill.jpg", quality=30)
    print("  created: blurry_pharmacy_bill.jpg")


# ── TC003 — Patient mismatch docs ────────────────────────────────────────────

def make_tc003_docs():
    # Prescription for Rajesh Kumar
    pdf = new_pdf()
    rx_header(pdf, "Dr. Arun Sharma, MBBS, MD", "KA/45678/2015",
              "City Medical Centre, Bengaluru")
    y = 46
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Patient: Rajesh Kumar                    Date: 01-Nov-2024")
    y += 14
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Diagnosis: Viral Fever")
    y += 10
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Rx: Tab Paracetamol 650mg - 1-1-1 x 5 days")
    pdf.output(f"{OUT}/prescription_rajesh_tc003.pdf")
    print("  created: prescription_rajesh_tc003.pdf")

    # Hospital bill for Arjun Mehta (wrong patient)
    pdf2 = new_pdf()
    bill_header(pdf2, "CITY MEDICAL CENTRE",
                "12 MG Road, Bengaluru - 560001")
    pdf2.set_font("Helvetica", "B", 12)
    pdf2.set_xy(15, 42)
    pdf2.cell(180, 8, "BILL / RECEIPT", align="C")
    y = 54
    pdf2.set_font("Helvetica", "", 9)
    pdf2.set_xy(18, y)
    pdf2.cell(174, 6, "Bill No: CMC/2024/08322          Date: 01-Nov-2024")
    pdf2.set_xy(18, y + 7)
    pdf2.cell(174, 6, "Patient Name: Arjun Mehta          Age/Gender: 28 / Male")
    pdf2.set_xy(18, y + 14)
    pdf2.cell(174, 6, "Referring Doctor: Dr. Arun Sharma")
    y += 28
    y = bill_items(pdf2, y, [("Consultation Fee", 1000)])
    total_row(pdf2, y + 2, 1000)
    pdf2.output(f"{OUT}/hospital_bill_arjun_mehta.pdf")
    print("  created: hospital_bill_arjun_mehta.pdf")


# ── TC004 — City Clinic bill for Rajesh Kumar ─────────────────────────────────

def make_hospital_bill_city_clinic():
    pdf = new_pdf()
    bill_header(pdf, "CITY MEDICAL CENTRE",
                "12 MG Road, Bengaluru - 560001  |  Ph: 080-41234567",
                "29AABCC1234D1Z5")
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(15, 46)
    pdf.cell(180, 8, "BILL / RECEIPT", align="C")
    y = 58
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Bill No: CMC/2024/08321          Date: 01-Nov-2024")
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "Patient Name: Rajesh Kumar         Age/Gender: 39 / Male")
    pdf.set_xy(18, y + 14)
    pdf.cell(174, 6, "Referring Doctor: Dr. Arun Sharma")
    y += 28
    y = bill_items(pdf, y, [
        ("Consultation Fee (OPD)", 1000),
        ("CBC (Complete Blood Count)", 200),
        ("Dengue NS1 Antigen Test", 300),
    ])
    total_row(pdf, y + 2, 1500)
    stamp(pdf, y + 14, "CASHIER STAMP")
    pdf.output(f"{OUT}/hospital_bill_city_clinic.pdf")
    print("  created: hospital_bill_city_clinic.pdf")


# ── TC005 — Vikram Joshi prescription + bill ──────────────────────────────────

def make_prescription_vikram():
    pdf = new_pdf()
    rx_header(pdf,
        "Dr. Sunil Mehta, MBBS, MD (General Medicine)",
        "GJ/56789/2014",
        "Mehta Clinic, Sarkhej Road, Ahmedabad - 380015",
        "+91-79-26587412"
    )
    y = 52
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Patient: Vikram Joshi                    Date: 15-Oct-2024")
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "Age: 45 years    Gender: Male")
    y += 20
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Diagnosis: Type 2 Diabetes Mellitus (T2DM)   HbA1c: 8.2%")
    y += 10
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Rx:")
    for i, line in enumerate([
        "1. Tab Metformin 500mg    -  1-0-1 x 30 days",
        "2. Tab Glimepiride 1mg    -  1-0-0 x 30 days",
        "3. Tab Vitamin B12 500mcg -  0-0-1 x 30 days",
    ]):
        pdf.set_xy(18, y + 7 + i * 7)
        pdf.cell(174, 6, f"  {line}")
    y += 35
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Diet: Low carbohydrate, avoid sugar")
    stamp(pdf, y + 10, "Reg. GJ/56789/2014")
    pdf.output(f"{OUT}/prescription_vikram_joshi.pdf")
    print("  created: prescription_vikram_joshi.pdf")


def make_hospital_bill_vikram():
    pdf = new_pdf()
    bill_header(pdf, "MEHTA CLINIC",
                "Sarkhej Road, Ahmedabad - 380015  |  Ph: 079-26587412",
                "24AABCM1234D1Z5")
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(15, 46)
    pdf.cell(180, 8, "CONSULTATION BILL", align="C")
    y = 58
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Bill No: MC/2024/04521           Date: 15-Oct-2024")
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "Patient Name: Vikram Joshi         Age/Gender: 45 / Male")
    pdf.set_xy(18, y + 14)
    pdf.cell(174, 6, "Referring Doctor: Dr. Sunil Mehta")
    y += 28
    y = bill_items(pdf, y, [("Consultation Fee (OPD)", 3000)])
    total_row(pdf, y + 2, 3000)
    pdf.output(f"{OUT}/hospital_bill_vikram_joshi.pdf")
    print("  created: hospital_bill_vikram_joshi.pdf")


# ── TC006 — Dental bill Priya Singh ──────────────────────────────────────────

def make_dental_bill():
    pdf = new_pdf()
    bill_header(pdf, "SMILE DENTAL CLINIC",
                "14 Koramangala 5th Block, Bengaluru - 560095",
                fill=(255, 245, 230))
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(15, 42)
    pdf.cell(180, 8, "DENTAL TREATMENT BILL", align="C")
    y = 54
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Bill No: SDC/2024/00521          Date: 15-Oct-2024")
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "Patient Name: Priya Singh          Age/Gender: 34 / Female")
    pdf.set_xy(18, y + 14)
    pdf.cell(174, 6, "Doctor: Dr. Rekha Nair, BDS, MDS")
    y += 28
    y = bill_items(pdf, y, [
        ("Root Canal Treatment (Tooth #36)", 8000),
        ("Teeth Whitening (Cosmetic)", 4000),
    ])
    total_row(pdf, y + 2, 12000)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_xy(18, y + 14)
    pdf.cell(180, 6, "Note: Cosmetic procedures may not be covered under insurance.")
    stamp(pdf, y + 22, "DENTAL STAMP", color=(180, 100, 60))
    pdf.output(f"{OUT}/dental_bill_smile_clinic.pdf")
    print("  created: dental_bill_smile_clinic.pdf")


# ── TC007 — MRI docs for Suresh Patil ────────────────────────────────────────

def make_prescription_mri():
    pdf = new_pdf()
    rx_header(pdf,
        "Dr. Venkat Rao, MBBS, MS (Orthopaedics)",
        "AP/67890/2017",
        "Spine and Joint Care Centre, Hyderabad - 500034",
        "+91-40-23456789"
    )
    y = 52
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Patient: Suresh Patil                    Date: 02-Nov-2024")
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "Age: 49 years    Gender: Male")
    y += 20
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Diagnosis: Suspected Lumbar Disc Herniation (L4-L5)")
    y += 10
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Rx:")
    for i, line in enumerate([
        "1. Tab Diclofenac 50mg    -  1-0-1 x 5 days (after food)",
        "2. Tab Pantoprazole 40mg  -  1-0-0 x 5 days",
        "3. Physiotherapy: 10 sessions",
    ]):
        pdf.set_xy(18, y + 7 + i * 7)
        pdf.cell(174, 6, f"  {line}")
    y += 35
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Investigations Required:")
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "  - MRI Lumbar Spine (with contrast)  --  URGENT")
    pdf.set_xy(18, y + 14)
    pdf.cell(174, 6, "Note: Insurance pre-authorization required for MRI.")
    stamp(pdf, y + 22, "Reg. AP/67890/2017")
    pdf.output(f"{OUT}/prescription_mri_suresh_patil.pdf")
    print("  created: prescription_mri_suresh_patil.pdf")


def make_lab_report_mri():
    pdf = new_pdf()
    bill_header(pdf, "PRECISION DIAGNOSTICS PVT LTD",
                "NABL Accredited  |  45 Jayanagar, Bengaluru  |  Ph: 080-22334455",
                fill=(245, 240, 255))
    y = 42
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Patient: Suresh Patil         Sample Date: 02-Nov-2024")
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "Ref Doctor: Dr. Venkat Rao    Sample ID: PD-2024-28931")
    y += 20
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(18, y)
    pdf.cell(80, 6, "INVESTIGATION")
    pdf.cell(50, 6, "FINDINGS")
    pdf.cell(47, 6, "REMARKS")
    y += 8
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(80, 7, "MRI Lumbar Spine")
    pdf.cell(50, 7, "L4-L5 Disc Herniation")
    pdf.cell(47, 7, "Nerve root compression")
    y += 14
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Impression: Moderate posterocentral disc herniation at L4-L5.")
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "Left-sided neural foraminal narrowing. Surgical opinion recommended.")
    y += 20
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Dr. Meena Pillai, MD (Radiology)  Reg: KA/89012/2018")
    stamp(pdf, y + 10, "NABL ACCREDITED", color=(80, 60, 180))
    pdf.output(f"{OUT}/lab_report_mri.pdf")
    print("  created: lab_report_mri.pdf")


def make_hospital_bill_mri():
    pdf = new_pdf()
    bill_header(pdf, "PRECISION DIAGNOSTICS PVT LTD",
                "45 Jayanagar, Bengaluru - 560041  |  GSTIN: 29AABCD5678F1Z1",
                fill=(245, 240, 255))
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(15, 42)
    pdf.cell(180, 8, "DIAGNOSTIC BILL", align="C")
    y = 54
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Bill No: PD/2024/09341           Date: 02-Nov-2024")
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "Patient Name: Suresh Patil         Age/Gender: 49 / Male")
    pdf.set_xy(18, y + 14)
    pdf.cell(174, 6, "Referring Doctor: Dr. Venkat Rao")
    y += 28
    y = bill_items(pdf, y, [("MRI Lumbar Spine (with contrast)", 15000)])
    total_row(pdf, y + 2, 15000)
    pdf.output(f"{OUT}/hospital_bill_mri.pdf")
    print("  created: hospital_bill_mri.pdf")


# ── TC008 — Amit Verma docs ───────────────────────────────────────────────────

def make_prescription_amit():
    pdf = new_pdf()
    rx_header(pdf,
        "Dr. R. Gupta, MBBS, MD (General Medicine)",
        "DL/34567/2016",
        "Gupta Clinic, Connaught Place, New Delhi - 110001"
    )
    y = 46
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Patient: Amit Verma                      Date: 20-Oct-2024")
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "Age: 38 years    Gender: Male")
    y += 20
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Diagnosis: Gastroenteritis")
    y += 10
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Rx:")
    for i, line in enumerate([
        "1. Azithromycin 500mg  -  1-0-1 x 5 days (after food)",
        "2. Probiotics (Lactobacillus)  -  0-1-0 x 7 days",
        "3. ORS Sachets  -  as required",
    ]):
        pdf.set_xy(18, y + 7 + i * 7)
        pdf.cell(174, 6, f"  {line}")
    stamp(pdf, y + 32, "Reg. DL/34567/2016")
    pdf.output(f"{OUT}/prescription_amit_verma.pdf")
    print("  created: prescription_amit_verma.pdf")


def make_hospital_bill_amit():
    pdf = new_pdf()
    bill_header(pdf, "CITY MEDICAL CENTRE",
                "12 MG Road, Bengaluru - 560001",
                "29AABCC1234D1Z5")
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(15, 46)
    pdf.cell(180, 8, "BILL / RECEIPT", align="C")
    y = 58
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Bill No: CMC/2024/08401          Date: 20-Oct-2024")
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "Patient Name: Amit Verma           Age/Gender: 38 / Male")
    pdf.set_xy(18, y + 14)
    pdf.cell(174, 6, "Referring Doctor: Dr. R. Gupta")
    y += 28
    y = bill_items(pdf, y, [
        ("Consultation Fee", 2000),
        ("Medicines (Antibiotics, Probiotics, ORS)", 5500),
    ])
    total_row(pdf, y + 2, 7500)
    pdf.output(f"{OUT}/hospital_bill_amit_verma.pdf")
    print("  created: hospital_bill_amit_verma.pdf")


# ── TC010 — Apollo bill + Deepak Shah prescription ───────────────────────────

def make_prescription_deepak():
    pdf = new_pdf()
    rx_header(pdf,
        "Dr. S. Iyer, MBBS, MD (General Medicine)",
        "TN/56789/2013",
        "Apollo Hospitals, Bannerghatta Road, Bengaluru - 560076"
    )
    y = 46
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Patient: Deepak Shah                     Date: 03-Nov-2024")
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "Age: 44 years    Gender: Male")
    y += 20
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Diagnosis: Acute Bronchitis")
    y += 10
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Rx:")
    for i, line in enumerate([
        "1. Amoxicillin 500mg    -  1-0-1 x 7 days",
        "2. Salbutamol Inhaler   -  2 puffs SOS",
        "3. Tab Paracetamol 650mg -  SOS for fever",
    ]):
        pdf.set_xy(18, y + 7 + i * 7)
        pdf.cell(174, 6, f"  {line}")
    stamp(pdf, y + 32, "Reg. TN/56789/2013")
    pdf.output(f"{OUT}/prescription_deepak_shah.pdf")
    print("  created: prescription_deepak_shah.pdf")


def make_hospital_bill_apollo():
    pdf = new_pdf()
    bill_header(pdf, "APOLLO HOSPITALS",
                "154/11 Bannerghatta Road, Bengaluru - 560076  |  Ph: 080-26304050",
                "29AABCA1234E1Z3",
                fill=(230, 240, 255))
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(15, 46)
    pdf.cell(180, 8, "OUTPATIENT BILL", align="C")
    y = 58
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Bill No: APL/2024/11032          Date: 03-Nov-2024")
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "Patient Name: Deepak Shah          Age/Gender: 44 / Male")
    pdf.set_xy(18, y + 14)
    pdf.cell(174, 6, "Referring Doctor: Dr. S. Iyer      Reg: TN/56789/2013")
    y += 28
    y = bill_items(pdf, y, [
        ("Consultation Fee (OPD)", 1500),
        ("Medicines (Amoxicillin 500mg x10, Salbutamol Inhaler)", 3000),
    ])
    total_row(pdf, y + 2, 4500)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_xy(18, y + 14)
    pdf.cell(174, 6,
             "Apollo Hospitals is a network hospital under your Plum Health Insurance policy.")
    stamp(pdf, y + 22, "APOLLO NETWORK", color=(60, 80, 180))
    pdf.output(f"{OUT}/hospital_bill_apollo.pdf")
    print("  created: hospital_bill_apollo.pdf")


# ── TC012 — Anita Desai bariatric docs ───────────────────────────────────────

def make_prescription_anita():
    pdf = new_pdf()
    rx_header(pdf,
        "Dr. P. Banerjee, MBBS, MS (General Surgery)",
        "WB/34567/2015",
        "Metro Bariatric Centre, Salt Lake, Kolkata - 700091",
        "+91-33-23456781"
    )
    y = 52
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Patient: Anita Desai                     Date: 18-Oct-2024")
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "Age: 31 years    Gender: Female")
    y += 20
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Diagnosis: Morbid Obesity  (BMI: 37.2 kg/m2)")
    y += 10
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Treatment Plan:")
    for i, line in enumerate([
        "1. Bariatric Consultation - initial assessment",
        "2. Personalised Diet and Nutrition Program (3 months)",
        "3. Psychological evaluation",
    ]):
        pdf.set_xy(18, y + 7 + i * 7)
        pdf.cell(174, 6, f"  {line}")
    y += 35
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Rx:")
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "  1. Tab Multivitamin   -  1-0-0 x 30 days")
    pdf.set_xy(18, y + 14)
    pdf.cell(174, 6, "  2. Tab Vitamin D3 60K -  once weekly x 8 weeks")
    stamp(pdf, y + 22, "Reg. WB/34567/2015")
    pdf.output(f"{OUT}/prescription_anita_desai.pdf")
    print("  created: prescription_anita_desai.pdf")


def make_hospital_bill_anita():
    pdf = new_pdf()
    bill_header(pdf, "METRO BARIATRIC CENTRE",
                "Salt Lake Sector V, Kolkata - 700091  |  Ph: 033-23456781",
                fill=(255, 240, 240))
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(15, 42)
    pdf.cell(180, 8, "TREATMENT BILL", align="C")
    y = 54
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Bill No: MBC/2024/00831          Date: 18-Oct-2024")
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "Patient Name: Anita Desai          Age/Gender: 31 / Female")
    pdf.set_xy(18, y + 14)
    pdf.cell(174, 6, "Doctor: Dr. P. Banerjee")
    y += 28
    y = bill_items(pdf, y, [
        ("Bariatric Consultation", 3000),
        ("Personalised Diet and Nutrition Program", 5000),
    ])
    total_row(pdf, y + 2, 8000)
    pdf.output(f"{OUT}/hospital_bill_anita_desai.pdf")
    print("  created: hospital_bill_anita_desai.pdf")


# ── TC002 — Pharmacy claim for Sneha Reddy ───────────────────────────────────

def make_prescription_sneha():
    pdf = new_pdf()
    rx_header(pdf,
        "Dr. K. Sharma, MBBS, MD",
        "KA/22334/2018",
        "Sharma Clinic, Brigade Road, Bengaluru - 560001"
    )
    y = 46
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Patient: Sneha Reddy                     Date: 25-Oct-2024")
    pdf.set_xy(18, y + 7)
    pdf.cell(174, 6, "Age: 29 years    Gender: Female")
    y += 20
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Diagnosis: Upper Respiratory Tract Infection")
    y += 10
    pdf.set_xy(18, y)
    pdf.cell(174, 6, "Rx:")
    for i, line in enumerate([
        "1. Azithromycin 500mg  -  1-0-0 x 3 days",
        "2. Pantoprazole 40mg   -  1-0-0 x 5 days",
        "3. Cetirizine 10mg     -  0-0-1 x 5 days",
    ]):
        pdf.set_xy(18, y + 7 + i * 7)
        pdf.cell(174, 6, f"  {line}")
    stamp(pdf, y + 32, "Reg. KA/22334/2018")
    pdf.output(f"{OUT}/prescription_sneha_reddy.pdf")
    print("  created: prescription_sneha_reddy.pdf")


# ── Run all ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Generating sample documents into: {OUT}/")
    print()

    print("TC001 + TC004 — Rajesh Kumar")
    make_prescription_rajesh()
    make_hospital_bill_city_clinic()
    make_prescription_wrong_second()

    print()
    print("TC002 — Sneha Reddy (Pharmacy)")
    make_prescription_sneha()
    make_blurry_pharmacy_bill()

    print()
    print("TC003 — Patient mismatch")
    make_tc003_docs()

    print()
    print("TC005 — Vikram Joshi (Diabetes)")
    make_prescription_vikram()
    make_hospital_bill_vikram()

    print()
    print("TC006 — Priya Singh (Dental)")
    make_dental_bill()

    print()
    print("TC007 — Suresh Patil (MRI)")
    make_prescription_mri()
    make_lab_report_mri()
    make_hospital_bill_mri()

    print()
    print("TC008 — Amit Verma (Per-claim limit)")
    make_prescription_amit()
    make_hospital_bill_amit()

    print()
    print("TC010 — Deepak Shah (Apollo network)")
    make_prescription_deepak()
    make_hospital_bill_apollo()

    print()
    print("TC012 — Anita Desai (Bariatric excluded)")
    make_prescription_anita()
    make_hospital_bill_anita()

    import os
    count = len([f for f in os.listdir(OUT) if f != "generate_docs.py"])
    print(f"\nDone. {count} files in sample_docs/")
    print()
    print("Note: TC009 and TC011 are tested via Swagger/JSON (no PDFs needed)")
    print("Note: TC003 uses prescription_rajesh_tc003.pdf + hospital_bill_arjun_mehta.pdf")