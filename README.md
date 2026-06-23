# ARCSATisfied
Data reduction for the APO ARCSAT

## Quick Start

```bash
python -m pip install -e ".[test]"
arcsatisfied reduce /path/to/arcsat/night
```

By default, products are written beside the input night in `reduced/`:

- `data/`: reduced science FITS files
- `cals/`: master bias, dark-rate, and per-filter flats
- `catalog/`: FITS header catalog, header JSONL archive, and Horizons CSVs
- `logs/`: run summary plus reduction and ASTAP result logs

Useful development/validation form:

```bash
env PYTHONPATH=src /Users/colinchandler/opt/anaconda3/envs/COC/bin/python \
  -m arcsatisfied reduce /path/to/arcsat/night \
  --output-dir /private/tmp/arcsatisfied_smoke \
  --overwrite --no-cosmic-rays --skip-astap
```

The reducer classifies ARCSAT frames from `IMAGETYP`, builds sigma-clipped
master calibrations, reduces `LIGHT` images, preserves FITS headers, and
records per-file provenance. Horizons enrichment is enabled by default using
Apache Point Observatory site code `705`; use `--skip-horizons` to stay fully
offline. ASTAP WCS solving is enabled by default when pointing metadata is
present; per-file ASTAP failures are logged and do not stop the run.
