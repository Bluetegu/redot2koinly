from pathlib import Path
import csv

from redot2koinly.convert import run as run_convert

ROOT = Path(__file__).parent


def read_csv_rows(p: Path):
    with p.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_eth_matches_expected(tmp_path):
    out = tmp_path / "eth_out.csv"
    img = ROOT / "eth.jpg"
    expected = ROOT / "eth_expected.csv"
    assert img.exists(), f"Missing test image: {img}"
    assert expected.exists(), f"Missing expected CSV: {expected}"

    stats = run_convert(input_path=str(img), output_file=str(out))
    assert out.exists()

    produced = read_csv_rows(out)
    golden = read_csv_rows(expected)
    assert produced == golden, "Produced CSV does not match expected output for eth.jpg"
    
    # Verify expected stats for eth.jpg
    assert stats.duplicates_removed == 0  # First run should have no duplicates
    assert stats.record_errors == 0  # eth.jpg should parse cleanly
    assert stats.records_read == 6  # Should read 6 transaction records
    assert stats.files_processed == 1
    assert stats.files_ignored == 0

