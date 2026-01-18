"""Command-line interface for redot2koinly."""
import argparse
import sys

from . import __version__
from . import convert


def build_parser():
    p = argparse.ArgumentParser(description="Convert Redotpay screenshots to Koinly CSV")
    p.add_argument("--input", "-i", required=False, default="data",
                   help="Input image file or directory (no recursion). Defaults to 'data'.")
    p.add_argument("--output", "-o", required=False, default="redotpay.csv",
                   help="Output CSV filename. Default: redotpay.csv")
    p.add_argument("--config", "-c", required=False, help="Path to JSON config file")
    p.add_argument("--timezone", "-z", required=False, default="Asia/Jerusalem",
                   help="Timezone of the Redotpay screenshots. Default: Asia/Jerusalem (IST)")
    p.add_argument("--year", "-y", required=False, type=int, default=2025,
                   help="Transaction year to apply to dates in screenshots. Default: 2025")
    p.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    p.add_argument("--print-logs", action="store_true", help="Print log messages to screen")
    p.add_argument("--version", action="version", version=__version__)
    return p


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    stats = convert.run(
        input_path=args.input,
        output_file=args.output,
        config_path=args.config,
        timezone=args.timezone,
        year=args.year,
        verbose=args.verbose,
        print_logs_to_screen=args.print_logs,
    )
    # Stats are already printed by convert.run, just return for potential use


if __name__ == "__main__":
    main()
