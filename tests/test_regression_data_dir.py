from pathlib import Path
import csv

from redot2koinly.convert import run as run_convert

ROOT = Path(__file__).parent


def read_csv_rows(p: Path):
    with p.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_data_dir_matches_expected(tmp_path):
    out = tmp_path / "data_out.csv"
    data_dir = ROOT / "data"
    expected = ROOT / "data_expected.csv"
    assert data_dir.exists(), f"Missing test data directory: {data_dir}"
    assert expected.exists(), f"Missing expected CSV: {expected}"

    run_convert(input_path=str(data_dir), output_file=str(out))
    assert out.exists()

    produced = read_csv_rows(out)
    golden = read_csv_rows(expected)
    assert produced == golden, "Produced CSV does not match expected output for tests/data directory"
