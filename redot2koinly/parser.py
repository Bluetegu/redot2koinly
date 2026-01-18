"""Parse OCR text into transaction records (stubs)."""
import re
from typing import List, Tuple, Dict

from . import logger

# OCR confidence thresholds
MIN_MERCHANT_CONFIDENCE = 0.15  # Lower threshold to handle partially garbled but readable merchant names
MIN_TIME_CONFIDENCE = 0.19  # Slightly lower than 0.2 to handle floating-point precision


def _centroid(bbox):
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _group_by_lines(tokens, y_tol=25):
    # tokens: list of dicts with keys x,y,text
    tokens = sorted(tokens, key=lambda t: t["y"])
    lines = []
    for t in tokens:
        if not lines:
            lines.append([t])
            continue
        last = lines[-1]
        if abs(t["y"] - last[-1]["y"]) <= y_tol:
            last.append(t)
        else:
            lines.append([t])
    # sort tokens in each line by x
    out_lines = []
    for grp in lines:
        grp_sorted = sorted(grp, key=lambda t: t["x"])
        line_text = " ".join([g["text"] for g in grp_sorted])
        out_lines.append({"y": sum(g["y"] for g in grp_sorted) / len(grp_sorted),
                          "text": line_text,
                          "tokens": grp_sorted})
    return out_lines


DATE_LINE_RE = re.compile(r"^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s*[,.;]\s+[A-Za-z]{3}\s+\d{1,2}")
# Enhanced time pattern: recognize prefix (4 digits or Wallet) + space + time
# Time is exactly 2 digits for hour, minute, and second
# Separators: one or two characters from ':', ';', ' ', '*', '.'
TIME_RE = re.compile(r"(?:\b\d{4}\b|Wallet)\s+(\d{2}[:.;* ]{1,2}\d{2}[:.;* ]{1,2}\d{2})")
# allow leading + - ~ and unicode minus variants
AMOUNT_RE = re.compile(r"([+\-~\u2212\u2013]?\d+\.\d+)")
CURRENCY_RE = re.compile(r"\b([A-Z]{3})\b")


def parse_easyocr_detections(detections, default_year: int) -> Tuple[List[Dict], int]:
    """Parse EasyOCR detections (bbox, text, conf) into records.

    Returns (records, errors).
    """
    tokens = []
    max_x = 0  # Track image width for filtering amount tokens
    for det in detections:
        try:
            bbox, txt, conf = det
        except Exception:
            # Fallback if EasyOCR returns (bbox, text) without confidence
            bbox, txt = det[0], det[1]
            conf = 0.0
        
        # Skip extremely low confidence detections (below 0.1) as they're likely noise
        if conf < 0.1:
            continue
            
        cx, cy = _centroid(bbox)
        # Track maximum x coordinate to estimate image width
        if bbox:
            token_max_x = max(p[0] for p in bbox)
            if token_max_x > max_x:
                max_x = token_max_x
        tokens.append({"x": cx, "y": cy, "text": txt.strip(), "conf": conf, "bbox": bbox})

    lines = _group_by_lines(tokens, y_tol=30)
    records = []
    errors = 0
    current_date = None
    for i, line in enumerate(lines):
        txt = line["text"].strip()
        if not txt:
            continue
        if txt.lower().startswith("no more records"):
            break
        if DATE_LINE_RE.match(txt):
            current_date = txt
            continue

        # Strict mode: only parse records when a date anchor exists
        if not current_date:
            continue

        # require an amount token in this line (prefer rightmost amount token)
        # but only consider tokens on the right half of the image to avoid time strings
        amount_token = None
        for tok in reversed(line.get("tokens", [])):
            if AMOUNT_RE.search(tok["text"]) and tok.get("x", 0) > max_x * 0.5:
                amount_token = tok
                break
        if not amount_token:
            # not a record line under strict rules
            continue

        # normalize token text and extract amount+currency strictly from same token
        ttxt = amount_token["text"].replace('~', '-').replace('\u2212', '-').replace('\u2013', '-')
        m_amt_cur = re.search(r"([+\-]?\d+\.\d+)\s*([A-Z]{3})\b", ttxt)
        if m_amt_cur:
            amount_val = m_amt_cur.group(1)
            currency = m_amt_cur.group(2)
        else:
            # If currency is not present in the same token, that's a strict parse error
            m_amount = AMOUNT_RE.search(ttxt)
            amount_val = m_amount.group(1) if m_amount else ""
            currency = ""

        # merchant and prefix+time should be tokens left of the amount token.
        # Include tokens in close vertical vicinity (y distance) to handle nearby bboxes
        y_vicinity = 40
        left_tokens = [t for t in tokens if abs(t["y"] - amount_token["y"]) <= y_vicinity and t["x"] < amount_token["x"]]
        
        merchant = ""
        prefix_time = ""
        # determine sign from amount token text
        sign_negative = bool(re.search(r"[\-\u2212\u2013]|^\-", ttxt))
        sign_positive = bool(re.search(r"\+", ttxt)) and not sign_negative

        if left_tokens:
            # sort left tokens by x (left-to-right)
            left_tokens = sorted(left_tokens, key=lambda t: t.get("x", 0))
            # also build an expanded left-token set to find time tokens that may sit below merchant
            left_tokens_expanded = [t for t in tokens if t.get("x", 0) < amount_token.get("x", 0) and abs(t.get("y", 0) - amount_token.get("y", 0)) <= (y_vicinity * 2)]
            left_tokens_expanded = sorted(left_tokens_expanded, key=lambda t: t.get("x", 0))

            # Candidates for time/prefix must contain a time pattern or (for negative) a 4-digit prefix
            # Apply lower confidence threshold for time tokens as they can be harder to OCR
            time_candidates = []
            for idx, lt in enumerate(left_tokens_expanded):
                # Skip time tokens with confidence below time threshold
                if lt.get("conf", 0) < MIN_TIME_CONFIDENCE:
                    continue
                    
                text = lt["text"]
                has_time = bool(TIME_RE.search(text))
                has_4dig = bool(re.search(r"\b\d{4}\b", text))
                
                # Only consider tokens that actually have time patterns or relevant prefixes
                is_time_relevant = False
                score = 0
                
                if has_time:
                    score += 10
                    is_time_relevant = True
                if sign_negative and has_4dig:
                    score += 5
                    is_time_relevant = True
                if sign_positive and re.search(r"\bWallet\b", text, re.IGNORECASE):
                    score += 5
                    is_time_relevant = True
                
                # Only add confidence score if the token is actually time-relevant
                if is_time_relevant:
                    conf_score = int(round(lt.get("conf", 0) * 10))
                    score += conf_score
                    time_candidates.append((score, idx, lt))

            # choose highest-scoring candidate (prefer rightmost among equals)
            time_idx = None
            time_tok = None
            if time_candidates:
                time_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
                _, time_idx, time_tok = time_candidates[0]
                prefix_time = time_tok["text"].strip()

            # Merchant selection should work whether or not a time token was found.
            # If a time token exists, merchant pool is tokens above it; otherwise use all left_tokens.
            if time_tok is not None:
                merchant_pool = [t for t in left_tokens if t.get("y", 0) < time_tok.get("y", 0)]
            else:
                merchant_pool = list(left_tokens)

            # Prefer tokens that look like merchant names: contain alphabetic chars.
            # Exclude icon-like tokens (no letters) and prefer higher confidence, longer text, and larger x.
            # Also filter out tokens in leftmost 10% of image (likely icons/UI elements)
            # Apply merchant confidence threshold only to merchant candidates
            icon_threshold_x = max_x * 0.1 if max_x > 0 else 100
            merchant_candidates = [t for t in merchant_pool 
                                 if re.search(r"[A-Za-z]", t["text"])
                                 and t.get("x", 0) > icon_threshold_x
                                 and t.get("conf", 0) >= MIN_MERCHANT_CONFIDENCE]

            if merchant_candidates:
                # Sort candidates by x-coordinate (left to right) to handle multi-token merchant names
                merchant_candidates.sort(key=lambda t: t.get("x", 0))
                
                # Try to combine adjacent merchant tokens that might form a complete name
                combined_tokens = []
                for i, token in enumerate(merchant_candidates):
                    # Check if this token is horizontally adjacent to the previous one
                    if combined_tokens:
                        prev_token = combined_tokens[-1]
                        
                        # Calculate actual gap between end of previous token and start of current token
                        prev_bbox = prev_token.get("bbox", [])
                        curr_bbox = token.get("bbox", [])
                        
                        # Same line check
                        same_line = abs(token.get("y", 0) - prev_token.get("y", 0)) <= 20
                        
                        # Calculate horizontal gap between token boundaries
                        if prev_bbox and curr_bbox and same_line:
                            prev_max_x = max(p[0] for p in prev_bbox)  # Right edge of previous token
                            curr_min_x = min(p[0] for p in curr_bbox)  # Left edge of current token
                            horizontal_gap = curr_min_x - prev_max_x
                            
                            # Only combine if gap is tight and both tokens have good confidence
                            prev_conf = prev_token.get("conf", 0)
                            curr_conf = token.get("conf", 0)
                            if (-10 <= horizontal_gap <= 10 and 
                                prev_conf > 0.4 and curr_conf > 0.4):
                                # Combine with previous token, keep previous token's x position
                                combined_text = f"{prev_token['text']} {token['text']}"
                                combined_tokens[-1] = {
                                    **prev_token,
                                    "text": combined_text
                                    # Keep original x position from prev_token
                                }
                                continue
                        
                    # Start new merchant token (either first token or not adjacent)
                    combined_tokens.append(token)
                
                # Choose best combined token by (confidence, length)
                def selection_key(t):
                    conf_rounded = round(t.get("conf", 0), 1)
                    text_length = len(t.get("text", ""))
                    return (conf_rounded, text_length)
                
                best = max(combined_tokens, key=selection_key)
                merchant = best["text"].strip()
                # Remove non-alphanumeric characters from the beginning
                merchant = re.sub(r'^[^a-zA-Z0-9]+', '', merchant)
            else:
                # strict mode: do not fallback to joining multiple tokens or icons.
                # Treat missing single-token merchant as parse failure by leaving merchant empty.
                merchant = ""

        # alignment check: amount token must be to the right of left tokens' rightmost edge
        amount_left_x = min(p[0] for p in amount_token.get("bbox", [])) if amount_token.get("bbox") else amount_token.get("x")
        left_max_right = 0
        for lt in left_tokens:
            if lt.get("bbox"):
                maxx = max(p[0] for p in lt["bbox"])
            else:
                maxx = lt.get("x", 0)
            if maxx > left_max_right:
                left_max_right = maxx
        aligned_right = amount_left_x > (left_max_right + 5)

        # normalize time
        time_norm = None
        if prefix_time:
            mt = TIME_RE.search(prefix_time)
            if mt:
                # Normalize all separators to colons and remove extra spaces
                time_str = mt.group(1)
                # Replace separators with colons (including * which can be either separator or digit corruption)
                time_str = re.sub(r'[:.;* ]+', ':', time_str)    # Replace separator sequences with single :
                # Clean up any remaining OCR artifacts after separator processing
                time_str = re.sub(r':+', ':', time_str)          # Replace multiple colons with single colon
                time_norm = time_str

        parse_error = False
        if not merchant:
            parse_error = True
        if not amount_val:
            parse_error = True
        if not currency:
            parse_error = True
        if not time_norm:
            parse_error = True
        if not aligned_right:
            parse_error = True

        if parse_error:
            errors += 1

        # Always append record (both valid and invalid) for counting purposes
        records.append({
            "date_line": current_date,
            "time": time_norm if time_norm else "",
            "amount": amount_val if amount_val else "",
            "currency": currency if currency else "",
            "merchant": merchant,
            "_parse_error": parse_error  # flag to indicate if this record had parsing errors
        })
    return records, errors
