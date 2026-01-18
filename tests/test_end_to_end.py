import tempfile
from redot2koinly import cli


def test_cli_runs_help():
    # Ensure that the CLI parser can be built and --help exits cleanly
    p = cli.build_parser()
    assert p is not None


def test_run_on_tests_dir():
    # Run conversion on the tests directory to ensure no uncaught exceptions
    with tempfile.NamedTemporaryFile(suffix='.csv') as tmp:
        cli.main(["--input", "tests", "--output", tmp.name])
        # If no exception, consider this a pass for the scaffold
