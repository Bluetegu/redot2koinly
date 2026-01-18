from pathlib import Path
import csv

from redot2koinly.convert import run as run_convert

ROOT = Path(__file__).parent


def read_csv_rows(p: Path):
    with p.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_incremental_runs_dedupe_and_sort(tmp_path):
    out = tmp_path / "eth_out.csv"
    img = ROOT / "eth.jpg"
    expected = ROOT / "eth_expected.csv"
    assert img.exists(), f"Missing test image: {img}"
    assert expected.exists(), f"Missing expected CSV: {expected}"

    # First run: produce initial CSV
    stats1 = run_convert(input_path=str(img), output_file=str(out))
    assert out.exists()
    produced1 = read_csv_rows(out)
    golden = read_csv_rows(expected)
    assert produced1 == golden
    
    # Verify first run stats: no duplicates since it's initial creation
    assert stats1.duplicates_removed == 0
    assert stats1.records_read > 0
    assert stats1.record_errors == 0  # eth.jpg should have no errors

    # Second run on same output and same input: should find all records as duplicates
    stats2 = run_convert(input_path=str(img), output_file=str(out))
    produced2 = read_csv_rows(out)
    assert produced2 == golden
    
    # Verify second run stats: all valid records should be duplicates
    expected_duplicates = len([row for row in produced1 if row['Koinly Date']])  # count valid records
    assert stats2.duplicates_removed == expected_duplicates
    assert stats2.records_read == stats1.records_read  # same number of records read
    assert stats2.record_errors == 0
