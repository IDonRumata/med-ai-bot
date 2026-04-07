import fitz  # PyMuPDF

MAX_SCAN_PAGES = 10  # Vision API limit per PDF


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF locally to save API tokens."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


def get_pdf_page_count(pdf_bytes: bytes) -> int:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    count = len(doc)
    doc.close()
    return count


def pdf_pages_to_images(pdf_bytes: bytes, dpi: int = 180) -> list[bytes]:
    """Convert all PDF pages to PNG images for Vision API.
    Limits to MAX_SCAN_PAGES to control cost."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for i, page in enumerate(doc):
        if i >= MAX_SCAN_PAGES:
            break
        pix = page.get_pixmap(dpi=dpi)
        images.append(pix.tobytes("png"))
    doc.close()
    return images
