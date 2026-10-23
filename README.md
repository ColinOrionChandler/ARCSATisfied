# ARCSATisfied

Quick CCD reduction and catalog enrichment for APO ARCSAT FITS data.

## Install and run

Python 3.10+ is required. Install from a clone of this repository:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install .
arcsatisfied reduce /path/to/arcsat/night
```

An offline run with explicit output location:

```bash
python -m arcsatisfied reduce /path/to/arcsat/night \
  --output-dir /path/to/output \
  --skip-horizons --skip-astap --no-cosmic-rays
```

Products default to `INPUT_DIR/reduced/`: `data/` contains reduced science FITS,
`cals/` contains master calibrations, `catalog/` contains header and Horizons
records, and `logs/` contains summaries and per-file results. Inspect those
results for individual failures. Existing products are reused unless
`--overwrite` is requested.

The reducer classifies frames from `IMAGETYP`, builds sigma-clipped master
calibrations, and preserves FITS headers with added provenance. Supply compatible
calibrations for the science frames' shape and binning. Horizons queries use APO
site code `705` by default. ASTAP and its star catalog are separate installations;
use `--astap-path` or put `astap` on `PATH`. Missing or failed solutions are logged.

Run `arcsatisfied reduce --help` for all options. See the
[usage guide](docs/usage.rst), [development guide](DEVELOPMENT_GUIDE.md), and
[service and release setup](SERVICE_SETUP.md).

## Development

```bash
python -m pip install -e '.[dev]'
python -m pip install -r docs/requirements.txt
pre-commit install
python -m pytest
pre-commit run --all-files
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

The existing `.[test]` extra remains available for test-only environments.
Packaging and automation are based on the
[LINCC Frameworks Python Project Template](https://github.com/lincc-frameworks/python-project-template)
v2.3.0, tracked through Copier. Licensed under [BSD-3-Clause](LICENSE).
