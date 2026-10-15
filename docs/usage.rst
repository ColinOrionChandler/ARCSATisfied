Using the reducer
=================

Run the standard workflow::

   arcsatisfied reduce /path/to/arcsat/night

Equivalent module invocation::

   python -m arcsatisfied reduce /path/to/arcsat/night

For a local validation run::

   arcsatisfied reduce /path/to/arcsat/night \
     --output-dir /path/to/output \
     --skip-horizons --skip-astap --no-cosmic-rays

The default output directory is ``INPUT_DIR/reduced/``. Input FITS files are
read without rewriting their pixels. Existing reduction products are reused
unless ``--overwrite`` is supplied. Use a new output directory for independent
runs. Check the summary and per-file logs for failures; a completed command
does not guarantee every file was successfully reduced or solved.

Products
--------

* ``data/``: reduced science FITS, preserving input metadata and adding
  calibration provenance. Cosmic-ray cleaning adds a ``COSMICRAY_MASK`` extension.
* ``cals/``: master bias, dark rate, and normalized flats per filter.
* ``catalog/``: extracted header catalog, JSONL header archive, and Horizons CSVs.
* ``logs/``: run summary and reduction/ASTAP result logs.

The reducer uses ``IMAGETYP`` to classify frames, sigma-clipped median
calibrations, exposure-scaled dark subtraction, and per-filter flat correction.
Use calibration inputs compatible with the science frames' shape and binning;
the quick reducer does not partition a mixed night into detector configurations.

Object maps and Horizons
------------------------

Horizons queries are enabled by default with APO observer code ``705``.
Inspect the proposed target names before using ephemerides scientifically.
Provide explicit mappings when FITS labels are ambiguous; the original
``OBJECT`` label remains in the catalog and header archive.

A CSV mapping by object label::

   object,horizons_name
   header label,Vesta

Pass it with ``--object-map objects.csv``. Filename-based mappings use
``filename,horizons_name`` columns and take precedence over object mappings.
Use ``--horizons-id-type`` and ``--site-code`` to override query settings.
Query failures are recorded per source image.

Options
-------

Run ``arcsatisfied reduce --help`` for the full interface. Options include
``--output-dir``, ``--object-map``, ``--overwrite``, ``--no-cosmic-rays``,
``--skip-horizons``, ``--site-code``, ``--horizons-id-type``, ``--skip-astap``,
``--astap-path``, and ``--astap-timeout`` (120 seconds by default).
