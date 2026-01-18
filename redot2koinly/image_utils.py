"""Image I/O and basic preprocessing helpers."""
from pathlib import Path
from typing import List

from PIL import Image
import logging

logger = logging.getLogger("redot2koinly.image_utils")


# Supported image extensions
SUPPORTED_EXT = {".jpg", ".jpeg", ".png"}


def find_images(path: str) -> List[Path]:
    p = Path(path)
    if p.is_file():
        return [p]
    if p.is_dir():
        return [x for x in sorted(p.iterdir()) if x.suffix.lower() in SUPPORTED_EXT]
    return []


def open_image(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def preprocess_image(img: Image.Image) -> Image.Image:
    # Resize large images to a reasonable width
    max_width = 1600
    w, h = img.size
    if w > max_width:
        ratio = max_width / float(w)
        img = img.resize((int(w * ratio), int(h * ratio)))
    # Convert to grayscale and enhance contrast to improve OCR
    try:
        from PIL import ImageEnhance, ImageFilter
        img = img.convert("L")
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.6)
        img = img.filter(ImageFilter.MedianFilter(size=3))
    except Exception:
        # fall back to original if enhancements fail
        pass
    return img


def has_history_header(img: Image.Image) -> (bool, str):
    """OCR the top region and return (found, text).

    Returns a tuple: (bool_found, ocr_text_snippet).
    Uses EasyOCR detections in the header band only; if detections produce no
    output we return (False, "") to correctly flag missing header.
    """
    try:
        from . import ocr
        w, h = img.size
        # Use a slightly taller header band and keep original color for OCR
        top_h = max(60, int(h * 0.18))
        top_region = img.crop((0, 0, w, top_h))

        # Use EasyOCR detections only
        dets = ocr.easyocr_detections(top_region)
        if not dets:
            logger.debug("history detection: no detections in header band; returning False")
            return False, ""

        det_texts = [t[1] for t in dets if len(t) >= 2]
        det_join = " ".join(det_texts).strip()
        if "history" in det_join.lower():
            return True, det_join
        return False, det_join
    except Exception:
        logger.debug("history detection failed; conservative default False")
        return False, ""
