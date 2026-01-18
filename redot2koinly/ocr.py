"""OCR wrapper providing EasyOCR detections only."""
from typing import Optional
from PIL import Image
import logging

logger = logging.getLogger("redot2koinly.ocr")

_has_easyocr = False
_easy_reader = None

try:
    import easyocr
    _has_easyocr = True
except Exception:
    easyocr = None

# Removed: ocr_image_lines (no longer used in the codebase)


def easyocr_detections(pil_image: Image.Image):
    """Return EasyOCR detections as a list of (bbox, text, conf).

    Returns empty list if easyocr is not available.
    """
    if not _has_easyocr:
        return []
    global _easy_reader
    try:
        if _easy_reader is None:
            _easy_reader = easyocr.Reader(["en"], gpu=False)
        import numpy as np
        arr = np.asarray(pil_image)
        return _easy_reader.readtext(arr, mag_ratio=1.5)
    except Exception:
        logger.debug("easyocr detection failed")
        return []

