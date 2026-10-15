from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits
from test_arcsatisfied import make_small_night

import arcsatisfied


def test_version_matches_distribution_metadata() -> None:
    assert arcsatisfied.__version__ == version("arcsatisfied")


@pytest.fixture(params=["console", "module"])
def invocation(request):
    if request.param == "console":
        name = "arcsatisfied.exe" if os.name == "nt" else "arcsatisfied"
        return [str(Path(sysconfig.get_path("scripts")) / name)]
    return [sys.executable, "-m", "arcsatisfied"]


def invoke(command, cwd):
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, check=True)


def test_installed_cli_help(invocation, tmp_path: Path) -> None:
    result = invoke([*invocation, "reduce", "--help"], tmp_path)
    for option in ("--output-dir", "--skip-horizons", "--skip-astap", "--object-map"):
        assert option in result.stdout


def test_installed_cli_reduces_offline(invocation, tmp_path: Path) -> None:
    night = tmp_path / "night"
    night.mkdir()
    make_small_night(night)
    source = night / "vesta_g_20250516_041755.fits"
    original = source.read_bytes()
    output = tmp_path / "out"
    result = invoke(
        [
            *invocation,
            "reduce",
            str(night),
            "--output-dir",
            str(output),
            "--skip-horizons",
            "--skip-astap",
            "--no-cosmic-rays",
        ],
        tmp_path,
    )
    summary = json.loads(result.stdout)
    assert summary["reduced_ok_count"] == 1
    assert summary["science_count"] == 1
    reduced = output / "data" / "vesta_g_20250516_041755_reduced.fits"
    data, header = fits.getdata(reduced, header=True)
    # Fixture: median bias=12, dark rate=(20-12)/10=0.8, science exposure=5.
    # Median normalized flat: 1 in the interior, (88-16)/(110-16)=72/94 in column 0.
    expected = np.full((6, 6), 184.0)
    expected[:, 0] = 184 * 94 / 72
    np.testing.assert_allclose(data, expected, rtol=1e-6)
    for key in ("OBJECT", "DATE-OBS", "EXPTIME", "FILTER", "RA", "DEC", "INSTRUME", "TELESCOP"):
        assert header[key] == fits.getheader(source)[key]
    assert header["ARCRAW"] == source.name
    assert header["ARCBIAS"] == "master_bias.fits"
    assert header["ARCDARK"] == "master_dark_rate.fits"
    assert header["ARCFLAT"] == "master_flat_g.fits"
    assert header["ARCCR"] is False
    assert source.read_bytes() == original
