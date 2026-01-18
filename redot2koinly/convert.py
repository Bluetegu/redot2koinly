"""Main conversion runner: integrates utilities to produce Koinly CSV."""
from pathlib import Path
import csv
from zoneinfo import ZoneInfo
from datetime import datetime
from typing import List
import warnings
import contextlib

from . import image_utils, ocr, parser, config
from .logger import logger, setup_logging, Stats


def _to_utc_koinly(date_line: str, time_str: str, year: int, tz_name: str) -> str:
    """Convert date_line and time_str to UTC Koinly format.
    
    Args:
        date_line: Date string like 'Wed, Sep 3' or 'Mon; Dec 8' or 'Fri. Nov 21'
        time_str: Time string like '14:30:03'
        year: Year to use for date parsing
        tz_name: Timezone name for conversion
        
    Returns:
        UTC timestamp string in format "YYYY-MM-DD HH:MM UTC"
        
    Raises:
        Exception: If either date_line or time_str are empty/invalid, or if parsing fails.
                  Caller should catch exceptions and handle as date conversion failure.
    """
    # date_line example: 'Wed, Sep 3' or 'Mon; Dec 8' or 'Fri. Nov 21'
    # Strip day name and normalize punctuation before parsing
    parts = date_line.split(",", 1)[-1].strip()  # Handle comma
    if not parts or parts == date_line:  # No comma found, try semicolon
        parts = date_line.split(";", 1)[-1].strip()
    if not parts or parts == date_line:  # No semicolon found, try period
        parts = date_line.split(".", 1)[-1].strip()
    
    dt_str = f"{parts} {year} {time_str}"
    # parse like 'Sep 3 2025 14:30:03'
    dt = datetime.strptime(dt_str, "%b %d %Y %H:%M:%S")
    try:
        local = ZoneInfo(tz_name)
        dt = dt.replace(tzinfo=local)
        dt_utc = dt.astimezone(ZoneInfo("UTC"))
    except Exception:
        # fallback: naive -> assume UTC
        dt_utc = dt
    return dt_utc.strftime("%Y-%m-%d %H:%M UTC")


@contextlib.contextmanager
def _suppress_output_if_needed(print_logs_to_screen: bool):
    """Redirect warnings to log file if logs shouldn't go to screen."""
    if print_logs_to_screen:
        # Don't suppress anything
        yield
    else:
        # Capture warnings and redirect them to our logger
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            yield
            
            # Log captured warnings
            for warning in w:
                logger.warning("External library warning: %s", str(warning.message))


def run(input_path: str = "data", output_file: str = "redotpay.csv", config_path=None,
        timezone: str = "Asia/Jerusalem", year: int = 2025, verbose: bool = False,
        print_logs_to_screen: bool = False):
    # load config early so we can configure logging
    cfg = config.load_config(config_path) if config_path else config.Config()
    # Use highest debug level by default per project request
    debug_mode = True
    setup_logging(verbose=verbose, debug=debug_mode,
                         log_file=cfg.log_file, max_bytes=cfg.log_max_bytes,
                         backup_count=cfg.log_backup_count, 
                         console_output=print_logs_to_screen)
    stats = Stats()
    stats.start()

    image_paths = image_utils.find_images(input_path)
    processed_records = []
    # We'll perform deduplication after all records are collected
    stats.duplicates_removed = 0
    file_errors = {}  # Track errors per file

    for p in image_paths:
        print(f"Processing {p.name}")
        stats.files_processed += 1
        try:
            img = image_utils.open_image(p)
            img = image_utils.preprocess_image(img)
            with _suppress_output_if_needed(print_logs_to_screen):
                header_result = image_utils.has_history_header(img)
            if isinstance(header_result, tuple):
                header_found, header_text = header_result
            else:
                header_found, header_text = bool(header_result), ""
            logger.info("File %s: header found=%s", p.name, header_found)
            if header_text:
                logger.debug("Header OCR snippet: %s", header_text)
            if not header_found:
                stats.files_ignored += 1
                continue
            dets = []
            try:
                with _suppress_output_if_needed(print_logs_to_screen):
                    dets = ocr.easyocr_detections(img)
                if dets:
                    logger.debug("EasyOCR detections:")
                    for det in dets:
                        try:
                            bbox, t, conf = det
                        except Exception:
                            # Some EasyOCR modes may return (bbox, text) only
                            bbox, t = det[0], det[1]
                            conf = 0.0
                        logger.debug("  conf=%.2f text=%s bbox=%s", conf, t, bbox)
            except Exception:
                logger.exception("easyocr detection failed")
            # Prefer EasyOCR detections when available for layout-aware parsing
            recs = []
            errs = 0
            try:
                if dets:
                    recs, errs = parser.parse_easyocr_detections(dets, default_year=year)
                else:
                    logger.warning("No EasyOCR detections; skipping parsing for %s", p.name)
            except Exception:
                logger.exception("Parsing failed using EasyOCR detections")
                recs, errs = [], 0
            
            # Count all records found by parser as "records_read" regardless of validity
            stats.records_read += len(recs)
            
            # Count parser errors directly
            stats.record_errors += errs
            
            for r in recs:
                # Collect records with parse errors for later display
                if r.get("_parse_error", False):
                    if str(p) not in file_errors:
                        file_errors[str(p)] = []
                    
                    # Format error message with merchant first, then error description, then details
                    merchant = r.get("merchant", "").strip()
                    date_line = r.get("date_line", "")
                    time_field = r.get("time", "").strip()
                    amount = r.get("amount", "").strip()
                    currency = r.get("currency", "").strip()
                    
                    # Determine what's missing
                    missing = []
                    if not merchant:
                        missing.append("merchant")
                    if not time_field:
                        missing.append("time")
                    if not amount:
                        missing.append("amount")
                    if not currency:
                        missing.append("currency")
                    
                    error_desc = "Missing " + ", ".join(missing) if missing else "Parse error"
                    
                    # Format: [merchant] - [error] ([date], [time], [amount], [currency])
                    merchant_part = merchant if merchant else "Unknown merchant"
                    details_parts = []
                    if date_line:
                        details_parts.append(date_line)
                    if time_field:
                        details_parts.append(time_field)
                    if amount:
                        details_parts.append(amount)
                    if currency:
                        details_parts.append(currency)
                    
                    details = " ".join(details_parts) if details_parts else "No details"
                    error_details = f"{merchant_part} - {error_desc} ({details})"
                    
                    file_errors[str(p)].append(error_details)
                    logger.warning("Parse error record: %s", error_details)
                    continue
                    
                # Log extracted fields before conversion
                logger.debug("Extracted: date_line=%s time=%s merchant=%s amount=%s currency=%s",
                                    r.get("date_line"), r.get("time"), r.get("merchant"),
                                    r.get("amount"), r.get("currency"))
                # Attempt to build Koinly Date (UTC); if fails, mark as invalid
                try:
                    kdate = _to_utc_koinly(r["date_line"], r["time"], year, timezone)
                    logger.debug("Converted to UTC Koinly Date: %s", kdate)
                except Exception as e:
                    logger.debug("Date conversion failed: %s", e)
                    kdate = ""

                label = r.get("merchant", "").strip().upper()
                # If trailing non-alphanumeric characters exist, remove them together with
                # the last alphanumeric character (OCR may misread it). Append '...' to label.
                try:
                    import re
                    # Example: "Store5!!!" -> "Store..."
                    if re.search(r"[^A-Za-z0-9]+$", label):
                        label = re.sub(r"[A-Za-z0-9][^A-Za-z0-9]+$", "...", label).strip()
                except Exception:
                    pass
                amount = r.get("amount", "")
                currency = r.get("currency", "").strip().upper()
                time_field = r.get("time", "")

                # A record is valid only if kdate, amount, currency, and label are present
                is_valid = bool(kdate and amount and currency and label and time_field)
                if not is_valid:
                    # Only handle date conversion failures here (parse errors are already handled above)
                    # Date conversion failure: parsing succeeded but kdate conversion failed
                    if not kdate and amount and currency and label and time_field and r.get("date_line"):
                        # This is specifically a date conversion failure
                        stats.record_errors += 1
                        
                        if str(p) not in file_errors:
                            file_errors[str(p)] = []
                        
                        error_details = f"{label} - Date conversion failed ({r.get('date_line')}, {time_field}, {amount}, {currency})"
                        
                        file_errors[str(p)].append(error_details)
                        logger.warning("Date conversion failed: %s", error_details)
                    continue

                processed_records.append({
                    "kdate": kdate,
                    "amount": amount,
                    "currency": currency,
                    "label": label,
                    "txhash": "",
                    "valid": is_valid,
                })
        except Exception as e:
            stats.files_ignored += 1

    # Convert only valid records to final row format
    final_rows = []
    for rec in processed_records:
        if rec["valid"]:
            final_rows.append([rec["kdate"], rec["amount"], rec["currency"], rec["label"], rec["txhash"]])

    # sort by Koinly Date (valid dates first). Use a sort key that treats empty dates as very large.
    def sort_key(row):
        k = row[0]
        return k or "9999-12-31 23:59 UTC"

    final_rows.sort(key=sort_key)

    # Incremental mode: if output file exists, merge existing rows, deduplicate, and sort.
    out_p = Path(output_file)

    existing_rows: List[List[str]] = []
    if out_p.exists():
        try:
            with out_p.open("r", newline="", encoding="utf-8") as rf:
                reader = csv.reader(rf)
                header = next(reader, None)
                # Accept existing files that match expected header; otherwise, treat all as data rows
                expected_header = ["Koinly Date", "Amount", "Currency", "Label", "TxHash"]
                if header is not None:
                    if [h.strip() for h in header] != expected_header:
                        # Header doesn't match; include it back as a data row for safety
                        existing_rows.append(header)
                    # Read the remaining rows
                    for row in reader:
                        # Normalize row length to 5 columns
                        if len(row) < 5:
                            row = (row + [""] * 5)[:5]
                        elif len(row) > 5:
                            row = row[:5]
                        existing_rows.append(row)
                else:
                    # Empty file; nothing to merge
                    pass
        except Exception:
            # If reading fails for any reason, fall back to no existing rows
            existing_rows = []

    # Merge old + new rows and track which ones are truly new duplicates
    merged_rows = existing_rows + final_rows

    # Build set of existing keys for duplicate detection
    existing_keys = set()
    for row in existing_rows:
        # Normalize row to 5 fields
        if len(row) < 5:
            row = (row + [""] * 5)[:5]
        elif len(row) > 5:
            row = row[:5]
        key = (row[0], row[1], row[2], row[3][:6] if len(row[3]) >= 6 else row[3])
        existing_keys.add(key)

    # Deduplicate across all rows, but only count new records as duplicates
    seen = set()
    deduped_rows: List[List[str]] = []
    for i, row in enumerate(merged_rows):
        # Normalize row to 5 fields
        if len(row) < 5:
            row = (row + [""] * 5)[:5]
        elif len(row) > 5:
            row = row[:5]
        key = (row[0], row[1], row[2], row[3][:6] if len(row[3]) >= 6 else row[3])
        
        if key in seen:
            # This is a duplicate - check if it's a new record (from final_rows)
            if i >= len(existing_rows):  # This row came from final_rows (new records)
                stats.duplicates_removed += 1
            continue
            
        seen.add(key)
        deduped_rows.append(row)

    # Sort after deduplication
    deduped_rows.sort(key=sort_key)

    # Write back full CSV with header
    with out_p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Koinly Date", "Amount", "Currency", "Label", "TxHash"])
        writer.writerows(deduped_rows)

    # Print stats
    duration = stats.duration()
    logger.info("Processed %d files (ignored: %d) in %.2fs",
                       stats.files_processed, stats.files_ignored, duration)
    # records_written: count actual rows written to CSV
    records_written = len(deduped_rows)
    logger.info("Records read: %d, written: %d, duplicates: %d, errors: %d",
                       stats.records_read, records_written, stats.duplicates_removed, stats.record_errors)
    
    # Print error details per file if any errors were found
    if file_errors:
        logger.info("Files with errors:")
        for filename, errors in file_errors.items():
            logger.info("%s:", filename)
            for error in errors:
                logger.info("  %s", error)
    
    # Print separator and screen output (only show separator if logs were printed to screen)
    if print_logs_to_screen:
        print("\n" + "🔍 " + "="*56 + " 📊")
    print(f"Processed {stats.files_processed} files (ignored: {stats.files_ignored}) in {duration:.2f}s")
    print(f"Records read: {stats.records_read}, written: {records_written}, duplicates: {stats.duplicates_removed}, errors: {stats.record_errors}")
    
    # Print file error details to screen after the stats
    if file_errors:
        print("\nFiles with errors:")
        for filename, errors in file_errors.items():
            print(f"\n{filename}:")
            for error in errors:
                print(f"  {error}")
    
    return stats


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert receipt images to Koinly CSV")
    parser.add_argument("input", nargs="?", default="data", help="input image file or directory (e.g. eth.jpg)")
    parser.add_argument("-o", "--output", default="redotpay.csv", help="output CSV file")
    parser.add_argument("-c", "--config", default=None, help="path to config file")
    parser.add_argument("--tz", default="Asia/Jerusalem", help="timezone name for conversion")
    parser.add_argument("--year", type=int, default=2025, help="default year for parsed dates")
    parser.add_argument("-v", "--verbose", action="store_true", help="enable verbose logging")
    parser.add_argument("--print-logs", action="store_true", help="print log messages to screen")
    args = parser.parse_args()
    run(input_path=args.input, output_file=args.output, config_path=args.config,
        timezone=args.tz, year=args.year, verbose=args.verbose, 
        print_logs_to_screen=args.print_logs)
