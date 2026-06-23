from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .horizons import DEFAULT_SITE_CODE
from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arcsatisfied",
        description="Quick CCD reduction and catalog enrichment for APO ARCSAT FITS data.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    reduce_parser = subparsers.add_parser(
        "reduce",
        help="Catalog, calibrate, reduce, optionally query Horizons, and optionally run ASTAP.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    reduce_parser.add_argument("input_dir", type=Path, help="Directory containing ARCSAT FITS files.")
    reduce_parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output root. Defaults to INPUT_DIR/reduced.",
    )
    reduce_parser.add_argument("--object-map", type=Path, help="Optional CSV mapping objects or filenames to Horizons names.")
    reduce_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing products.")
    reduce_parser.add_argument("--no-cosmic-rays", action="store_true", help="Disable astroscrappy cosmic-ray cleaning.")
    reduce_parser.add_argument("--skip-horizons", action="store_true", help="Skip JPL Horizons queries.")
    reduce_parser.add_argument("--site-code", default=DEFAULT_SITE_CODE, help="Horizons observer location code.")
    reduce_parser.add_argument("--horizons-id-type", default="smallbody", help="Astroquery Horizons id_type.")
    reduce_parser.add_argument("--skip-astap", action="store_true", help="Skip ASTAP WCS solving.")
    reduce_parser.add_argument("--astap-path", type=Path, help="Explicit ASTAP executable path.")
    reduce_parser.add_argument("--astap-timeout", type=int, default=120, help="Per-file ASTAP timeout in seconds.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "reduce":
        try:
            summary = run_pipeline(
                args.input_dir,
                output_dir=args.output_dir,
                object_map=args.object_map,
                overwrite=args.overwrite,
                cosmic_rays=not args.no_cosmic_rays,
                run_horizons=not args.skip_horizons,
                site_code=args.site_code,
                horizons_id_type=args.horizons_id_type,
                run_astap=not args.skip_astap,
                astap_path=args.astap_path,
                astap_timeout=args.astap_timeout,
            )
        except Exception as exc:
            print(f"arcsatisfied: error: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    return 2
