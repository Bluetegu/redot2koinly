from pathlib import Path
import csv

from redot2koinly.convert import run as run_convert
from redot2koinly.image_utils import open_image, has_history_header

ROOT = Path(__file__).parent


def read_csv_rows(p: Path):
    with p.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_error2_no_header(tmp_path):
    img_path = ROOT / "error2.jpeg"
    assert img_path.exists(), f"Missing test image: {img_path}"
    img = open_image(img_path)
    found, _ = has_history_header(img)
    assert not found, "error2.jpeg should not have a 'History' header"

    out = tmp_path / "error2_out.csv"
    run_convert(input_path=str(img_path), output_file=str(out))
    assert out.exists()
    rows = read_csv_rows(out)
    # Should produce no data rows when header is missing
    assert rows == [], "Expected no parsed rows for error2.jpeg (missing header)"
