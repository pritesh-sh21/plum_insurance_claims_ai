"""
core/file_handler.py

Handles all file processing before documents reach the parser agent.

PDFs are sent directly to GPT-4o as base64 — no poppler/pdf2image needed.
GPT-4o natively understands PDF bytes encoded as base64.

Images (JPG/PNG) are processed via Pillow for blur detection,
then base64 encoded and sent as image_url messages.

Zero system dependencies — works on Windows, Mac, Linux, any cloud platform.
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field
from enum import Enum

from PIL import Image, ImageFilter


class FileType(str, Enum):
    PDF   = "PDF"
    IMAGE = "IMAGE"
    UNKNOWN = "UNKNOWN"


@dataclass
class PageContent:
    page_number:   int
    base64_data:   str    # base64 encoded content for GPT-4o
    media_type:    str    # "application/pdf" or "image/jpeg"
    width:         int
    height:        int
    blur_score:    float  # images only — higher = sharper
    is_degraded:   bool


@dataclass
class FileContent:
    file_id:   str
    file_name: str
    file_type: FileType
    pages:     list[PageContent] = field(default_factory=list)
    error:     str | None = None

    @property
    def is_readable(self) -> bool:
        if self.error:
            return False
        return len(self.pages) > 0

    @property
    def overall_blur_score(self) -> float:
        scores = [p.blur_score for p in self.pages if p.blur_score > 0]
        return sum(scores) / len(scores) if scores else 100.0

    @property
    def quality_label(self) -> str:
        score = self.overall_blur_score
        if score >= 2000:
            return "GOOD"
        elif score >= 800:
            return "DEGRADED"
        else:
            return "UNREADABLE"


# ── Main entry point ──────────────────────────────────────────────────────────

def process_file(
    file_bytes: bytes,
    file_id:    str,
    file_name:  str,
) -> FileContent:
    """
    Process uploaded file bytes into FileContent ready for GPT-4o.
    PDFs: base64 encoded directly — no conversion needed.
    Images: Pillow for blur detection + base64 encoding.
    Always returns FileContent — never raises.
    """
    file_type = _detect_file_type(file_bytes, file_name)

    if file_type == FileType.PDF:
        return _process_pdf(file_bytes, file_id, file_name)
    elif file_type == FileType.IMAGE:
        return _process_image(file_bytes, file_id, file_name)
    else:
        return FileContent(
            file_id=file_id,
            file_name=file_name,
            file_type=FileType.UNKNOWN,
            error=f"Unsupported file type: {file_name}. Upload PDF, JPG, or PNG.",
        )


# ── File type detection ───────────────────────────────────────────────────────

def _detect_file_type(file_bytes: bytes, file_name: str) -> FileType:
    # Magic bytes first — more reliable than extension
    if file_bytes[:4] == b"%PDF":
        return FileType.PDF
    if file_bytes[:2] in (b"\xff\xd8", b"\x89P"):  # JPEG or PNG
        return FileType.IMAGE

    # Extension fallback
    name = file_name.lower()
    if name.endswith(".pdf"):
        return FileType.PDF
    if any(name.endswith(e) for e in (".jpg", ".jpeg", ".png", ".webp")):
        return FileType.IMAGE

    return FileType.UNKNOWN


# ── PDF processing — direct base64, no poppler ───────────────────────────────

def _process_pdf(file_bytes: bytes, file_id: str, file_name: str) -> FileContent:
    """
    Convert PDF pages to JPEG images using pymupdf (pure Python, no poppler).
    Each page becomes a separate PageContent with base64 JPEG for GPT-4o vision.
    """
    try:
        import fitz  # pymupdf
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Render at 2x scale for better quality
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("jpeg")
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            pages.append(PageContent(
                page_number=page_num + 1,
                base64_data=b64,
                media_type="image/jpeg",
                width=pix.width,
                height=pix.height,
                blur_score=9999.0,  # PDFs assumed readable
                is_degraded=False,
            ))
        doc.close()
        return FileContent(
            file_id=file_id,
            file_name=file_name,
            file_type=FileType.PDF,
            pages=pages,
        )
    except Exception as e:
        return FileContent(
            file_id=file_id,
            file_name=file_name,
            file_type=FileType.PDF,
            error=f"PDF processing failed: {str(e)}",
        )


# ── Image processing ──────────────────────────────────────────────────────────

def _process_image(file_bytes: bytes, file_id: str, file_name: str) -> FileContent:
    try:
        img = Image.open(io.BytesIO(file_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Resize if too large — GPT-4o vision works well up to 2048px
        img = _resize_if_needed(img, max_dim=2048)

        # Encode to JPEG base64
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        blur_score  = _compute_blur_score(img)
        is_degraded = blur_score < 2000

        page = PageContent(
            page_number=1,
            base64_data=b64,
            media_type="image/jpeg",
            width=img.width,
            height=img.height,
            blur_score=round(blur_score, 1),
            is_degraded=is_degraded,
        )
        return FileContent(
            file_id=file_id,
            file_name=file_name,
            file_type=FileType.IMAGE,
            pages=[page],
        )
    except Exception as e:
        return FileContent(
            file_id=file_id,
            file_name=file_name,
            file_type=FileType.IMAGE,
            error=f"Image processing failed: {str(e)}",
        )


def _resize_if_needed(img: Image.Image, max_dim: int = 2048) -> Image.Image:
    w, h = img.size
    if max(w, h) <= max_dim:
        return img
    ratio = max_dim / max(w, h)
    return img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)


def _compute_blur_score(img: Image.Image) -> float:
    gray      = img.convert("L").resize((256, 256))
    edges     = gray.filter(ImageFilter.FIND_EDGES)
    import statistics
    pixels = list(edges.tobytes())
    if not pixels:
        return 100.0
    try:
        return statistics.variance(pixels)
    except Exception:
        return 100.0


# ── Build vision message content for GPT-4o ──────────────────────────────────

def build_vision_content(file_content: FileContent, prompt: str) -> list[dict]:
    """
    Build GPT-4o messages content list.
    All pages are sent as image/jpeg base64 data URIs.
    PDFs are pre-converted to JPEG pages by _process_pdf via pymupdf.
    """
    content: list[dict] = [{"type": "text", "text": prompt}]

    for page in file_content.pages:
        if page.is_degraded:
            content.append({
                "type": "text",
                "text": (
                    f"[Page {page.page_number} image quality is low "
                    f"(blur score: {page.blur_score:.0f}). "
                    f"Extract what you can and flag uncertain fields in warnings.]"
                ),
            })
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{page.base64_data}",
                "detail": "high",
            },
        })

    return content