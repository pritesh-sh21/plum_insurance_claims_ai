"""
Tests for core/file_handler.py and routers/upload.py

Tests the full real-file processing path:
  - PDF detection and page conversion
  - Image processing and blur detection
  - Quality labels (GOOD / DEGRADED / UNREADABLE)
  - Document type resolution from filename
  - Upload endpoint integration
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from pathlib import Path

from core.file_handler import (
    process_file, build_vision_content, FileType,
    _detect_file_type, _compute_blur_score,
)
from PIL import Image
import io

SAMPLE_DOCS = Path(__file__).parent.parent.parent / "sample_docs"


# ── File type detection ───────────────────────────────────────────────────────

def test_detect_pdf_by_magic_bytes():
    fake_pdf = b"%PDF-1.4 fake content"
    assert _detect_file_type(fake_pdf, "document.pdf") == FileType.PDF


def test_detect_jpeg_by_magic_bytes():
    fake_jpg = b"\xff\xd8\xff fake jpeg"
    assert _detect_file_type(fake_jpg, "photo.jpg") == FileType.IMAGE


def test_detect_png_by_magic_bytes():
    fake_png = b"\x89PNG fake png"
    assert _detect_file_type(fake_png, "scan.png") == FileType.IMAGE


def test_detect_by_extension_fallback():
    unknown_bytes = b"random bytes here"
    assert _detect_file_type(unknown_bytes, "bill.pdf") == FileType.PDF
    assert _detect_file_type(unknown_bytes, "photo.jpg") == FileType.IMAGE
    assert _detect_file_type(unknown_bytes, "unknown.xyz") == FileType.UNKNOWN


# ── Blur score ────────────────────────────────────────────────────────────────

def test_sharp_image_high_blur_score():
    """A clean white image with black text should score high (sharp)."""
    img = Image.new("RGB", (200, 200), "white")
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "Sharp text on white", fill="black")
    draw.rectangle([20, 50, 180, 150], outline="black", width=2)
    score = _compute_blur_score(img)
    assert score > 1000, f"Sharp image should score > 1000, got {score}"


def test_blurry_image_low_blur_score():
    """A heavily blurred image should score low."""
    img = Image.new("RGB", (200, 200), "white")
    from PIL import ImageFilter
    for _ in range(10):
        img = img.filter(ImageFilter.GaussianBlur(radius=5))
    score = _compute_blur_score(img)
    assert score < 2000, f"Blurry image should score < 2000, got {score}"


# ── Image processing ──────────────────────────────────────────────────────────

def test_process_valid_jpeg():
    """Create a clean JPEG in memory and process it."""
    img = Image.new("RGB", (400, 300), "white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    jpeg_bytes = buf.getvalue()

    result = process_file(jpeg_bytes, "F001", "test_bill.jpg")

    assert result.file_type == FileType.IMAGE
    assert result.error is None
    assert len(result.pages) == 1
    assert result.pages[0].base64_data  # has content
    assert result.pages[0].width == 400
    assert result.pages[0].height == 300


def test_process_rgba_image_converts_to_rgb():
    """RGBA images should be converted to RGB without error."""
    img = Image.new("RGBA", (200, 200), (255, 255, 255, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    result = process_file(png_bytes, "F002", "scan.png")
    assert result.error is None
    assert len(result.pages) == 1


def test_process_invalid_bytes_returns_error():
    """Garbage bytes should return FileContent with error, not raise."""
    result = process_file(b"not a real file", "F003", "broken.jpg")
    assert result.error is not None
    assert len(result.pages) == 0


# ── PDF processing ────────────────────────────────────────────────────────────

def test_process_real_prescription_pdf():
    """Process a real prescription PDF — no poppler needed, direct base64."""
    pdf_path = SAMPLE_DOCS / "prescription_rajesh_kumar.pdf"
    if not pdf_path.exists():
        pytest.skip("Sample docs not generated yet — run sample_docs/generate_docs.py")

    pdf_bytes = pdf_path.read_bytes()
    result = process_file(pdf_bytes, "F004", "prescription_rajesh_kumar.pdf")

    assert result.error is None, f"PDF processing error: {result.error}"
    assert result.file_type == FileType.PDF
    assert len(result.pages) == 1
    assert result.pages[0].base64_data   # has base64 content
    assert result.pages[0].media_type == "image/jpeg"  # pymupdf converts to JPEG
    assert result.is_readable


def test_process_real_hospital_bill_pdf():
    """Process the generated hospital bill PDF."""
    pdf_path = SAMPLE_DOCS / "hospital_bill_city_clinic.pdf"
    if not pdf_path.exists():
        pytest.skip("Sample docs not generated yet — run sample_docs/generate_docs.py")

    pdf_bytes = pdf_path.read_bytes()
    result = process_file(pdf_bytes, "F005", "hospital_bill_city_clinic.pdf")

    assert result.error is None
    assert len(result.pages) == 1
    assert result.pages[0].base64_data
    assert result.is_readable


def test_process_blurry_pharmacy_bill():
    """The blurry pharmacy bill JPG should be detected as DEGRADED or UNREADABLE."""
    jpg_path = SAMPLE_DOCS / "blurry_pharmacy_bill.jpg"
    if not jpg_path.exists():
        pytest.skip("Sample docs not generated yet — run sample_docs/generate_docs.py")

    jpg_bytes = jpg_path.read_bytes()
    result = process_file(jpg_bytes, "F006", "blurry_pharmacy_bill.jpg")

    assert result.error is None
    assert len(result.pages) == 1
    assert result.quality_label in ("DEGRADED", "UNREADABLE"), \
        f"Blurry bill should be DEGRADED or UNREADABLE, got {result.quality_label} (blur={result.overall_blur_score})"


# ── Vision content builder ────────────────────────────────────────────────────

def test_build_vision_content_structure():
    """Vision content should have text prompt + image_url entries."""
    img = Image.new("RGB", (200, 200), "white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    result = process_file(buf.getvalue(), "F007", "test.jpg")

    content = build_vision_content(result, "Extract fields from this document.")

    assert content[0]["type"] == "text"
    assert "Extract fields" in content[0]["text"]
    image_entries = [c for c in content if c["type"] == "image_url"]
    assert len(image_entries) == 1
    assert image_entries[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_build_vision_content_degraded_adds_warning():
    """Degraded pages should add a warning text entry before the image."""
    img = Image.new("RGB", (200, 200), "white")
    from PIL import ImageFilter
    for _ in range(15):
        img = img.filter(ImageFilter.GaussianBlur(radius=8))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    result = process_file(buf.getvalue(), "F008", "blurry.jpg")

    content = build_vision_content(result, "Extract fields.")
    text_entries = [c for c in content if c["type"] == "text"]

    if result.pages[0].is_degraded:
        # Should have a degraded warning text entry
        assert any("low quality" in t["text"].lower() or "blur" in t["text"].lower()
                   for t in text_entries)


# ── Quality label ─────────────────────────────────────────────────────────────

def test_quality_labels():
    from core.file_handler import FileContent, FileType, PageContent

    def make_fc(blur_score):
        fc = FileContent(file_id="x", file_name="x", file_type=FileType.IMAGE)
        fc.pages = [PageContent(
            page_number=1, base64_data="abc", media_type="image/jpeg",
            width=100, height=100,
            blur_score=blur_score,
            is_degraded=blur_score < 50,
        )]
        return fc

    assert make_fc(2500).quality_label == "GOOD"
    assert make_fc(1000).quality_label == "DEGRADED"
    assert make_fc(500).quality_label == "UNREADABLE"