"""Sphinx configuration for ARCSATisfied."""

from importlib.metadata import version as package_version
from pathlib import Path

project = "ARCSATisfied"
author = "Colin Orion Chandler"
copyright = "2026, Colin Orion Chandler"
release = package_version("arcsatisfied")
extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "autoapi.extension",
    "sphinx_copybutton",
    "myst_parser",
]
html_theme = "sphinx_rtd_theme"
html_theme_options = {"navigation_depth": 3}
exclude_patterns = ["_build"]
autoapi_dirs = [str(Path(__file__).resolve().parents[1] / "src")]
autoapi_ignore = ["*/__main__.py", "*/_version.py"]
autoapi_member_order = "bysource"
autoapi_add_toctree_entry = False
