Installation
============

Python 3.10 or newer is required. Tests cover Python 3.10–3.14 on Linux,
with an additional Python 3.12 job on macOS.

Install from the repository (no PyPI release has been published yet)::

   git clone https://github.com/ColinOrionChandler/ARCSATisfied.git
   cd ARCSATisfied
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install .
   arcsatisfied --help

On Windows, activate the environment with ``.venv\Scripts\activate``.
Dependencies are Astropy, Astroquery, Astro-SCRAPPY, NumPy, and pandas.

ASTAP
-----

Install `ASTAP <https://www.hnsky.org/astap.htm>`_ and its appropriate star
catalog separately. Put the executable on ``PATH`` or pass
``--astap-path /path/to/astap``. Solving requires RA/Dec pointing headers.
Missing executables, pointing metadata, and individual solver failures are
recorded in the results. Use ``--skip-astap`` to disable solving.

Offline operation
-----------------

Package installation requires access to dependencies unless already cached.
Once installed, ``--skip-horizons`` prevents ephemeris queries. The completely
local example in :doc:`usage` also disables ASTAP and cosmic-ray cleaning.
