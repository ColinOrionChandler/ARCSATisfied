from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from astropy.io import fits

from arcsatisfied.astap import run_astap_on_files
from arcsatisfied.catalog import catalog_directory
from arcsatisfied.horizons import query_horizons_for_catalog
from arcsatisfied.pipeline import run_pipeline


def write_fits(
    path: Path,
    data: np.ndarray,
    *,
    imagetyp: str,
    exptime: float,
    filt: str = "",
    obj: str = "",
    date_obs: str = "2025-05-16T04:17:56.000",
    ra: str = "14 38 24.71",
    dec: str = "-03 51 52.1",
) -> Path:
    header = fits.Header()
    header["IMAGETYP"] = imagetyp
    header["DATE-OBS"] = date_obs
    header["EXPTIME"] = exptime
    header["XBINNING"] = 1
    header["YBINNING"] = 1
    header["INSTRUME"] = "dcam-spare"
    header["TELESCOP"] = "ARCSAT 0.5-m"
    if filt:
        header["FILTER"] = filt
    if obj:
        header["OBJECT"] = obj
    if ra and dec:
        header["RA"] = ra
        header["DEC"] = dec
        header["OBJCTRA"] = ra
        header["OBJCTDEC"] = dec
    fits.PrimaryHDU(data=data.astype(np.float32), header=header).writeto(path, overwrite=True)
    return path


def make_small_night(root: Path) -> None:
    shape = (6, 6)
    for index, level in enumerate((10, 12, 14), start=1):
        write_fits(root / f"Bias_BIN1_{index}.fits", np.full(shape, level), imagetyp="BIAS", exptime=0)
    for index in range(2):
        write_fits(root / f"Dark_BIN1_{index}.fits", np.full(shape, 20), imagetyp="DARK", exptime=10)
    for index, scale in enumerate((1.0, 1.1, 1.2), start=1):
        flat = np.full(shape, 100 * scale)
        flat[:, 0] = 80 * scale
        write_fits(root / f"domeflat_g_{index}.fits", flat, imagetyp="FLAT", exptime=5, filt="g")
    write_fits(
        root / "vesta_g_20250516_041755.fits",
        np.full(shape, 200),
        imagetyp="LIGHT",
        exptime=5,
        filt="g",
        obj="vesta",
    )


def test_catalog_extracts_arcsat_fields_and_horizons_name(tmp_path: Path) -> None:
    make_small_night(tmp_path)
    catalog, headers = catalog_directory(tmp_path)

    assert len(catalog) == 9
    vesta = catalog[catalog["filename"] == "vesta_g_20250516_041755.fits"].iloc[0]
    assert vesta["frame_type"] == "LIGHT"
    assert vesta["object"] == "vesta"
    assert vesta["horizons_name"] == "vesta"
    assert vesta["filter"] == "g"
    assert vesta["datetime"].startswith("2025-05-16T04:17:58")
    assert len(headers) == 9


def test_pipeline_reduces_synthetic_night_without_network_or_astap(tmp_path: Path) -> None:
    input_dir = tmp_path / "night"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    make_small_night(input_dir)

    summary = run_pipeline(
        input_dir,
        output_dir=output_dir,
        cosmic_rays=False,
        run_horizons=False,
        run_astap=False,
    )

    assert summary["fits_count"] == 9
    assert summary["science_count"] == 1
    assert summary["reduced_ok_count"] == 1
    assert (output_dir / "cals" / "master_bias.fits").exists()
    assert (output_dir / "cals" / "master_dark_rate.fits").exists()
    assert (output_dir / "cals" / "master_flat_g.fits").exists()
    reduced = output_dir / "data" / "vesta_g_20250516_041755_reduced.fits"
    assert reduced.exists()
    reduced_data = fits.getdata(reduced)
    assert np.isfinite(reduced_data).all()
    catalog = pd.read_csv(output_dir / "catalog" / "arcsat_catalog.csv")
    assert catalog.loc[catalog["frame_type"] == "LIGHT", "reduction_status"].iloc[0] == "ok"


class FakeHorizons:
    def __init__(self, id: str, location: str, epochs: list[float], id_type: str | None):
        self.id = id
        self.location = location
        self.epochs = epochs
        self.id_type = id_type

    def ephemerides(self, cache: bool = False):
        if self.id == "bad":
            raise RuntimeError("unknown target")

        class Table:
            def to_pandas(self_nonlocal):
                return pd.DataFrame(
                    [
                        {
                            "targetname": "4 Vesta (A807 FA)",
                            "datetime_str": "2025-May-16 04:17:58.000",
                            "RA": 219.6033,
                            "DEC": -3.86446,
                            "V": 5.805,
                        }
                        for _ in self.epochs
                    ]
                )

        return Table()


def test_horizons_success_and_failure_are_row_level() -> None:
    catalog = pd.DataFrame(
        [
            {
                "filename": "vesta.fits",
                "frame_type": "LIGHT",
                "horizons_name": "vesta",
                "datetime": "2025-05-16T04:17:58.000",
            },
            {
                "filename": "bad.fits",
                "frame_type": "LIGHT",
                "horizons_name": "bad",
                "datetime": "2025-05-16T04:17:58.000",
            },
        ]
    )

    outputs = query_horizons_for_catalog(catalog, horizons_cls=FakeHorizons)

    assert len(outputs.results) == 1
    assert outputs.results.iloc[0]["targetname"] == "4 Vesta (A807 FA)"
    assert len(outputs.failures) == 1
    assert outputs.failures.iloc[0]["source_filename"] == "bad.fits"
    assert "unknown target" in outputs.failures.iloc[0]["error"]


def test_astap_adapter_records_success_and_failure(tmp_path: Path) -> None:
    image = write_fits(
        tmp_path / "image.fits",
        np.ones((4, 4)),
        imagetyp="LIGHT",
        exptime=1,
        filt="g",
        obj="vesta",
    )

    def ok_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="ok", stderr="")

    def fail_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 3, stdout="", stderr="no solution")

    ok = run_astap_on_files([image], astap_path="/bin/echo", runner=ok_runner)
    failed = run_astap_on_files([image], astap_path="/bin/echo", runner=fail_runner)

    assert ok[0].status == "ok"
    assert failed[0].status == "error"
    assert "no solution" in failed[0].error


def test_object_map_overrides_header_object(tmp_path: Path) -> None:
    image = write_fits(
        tmp_path / "science.fits",
        np.ones((4, 4)),
        imagetyp="LIGHT",
        exptime=1,
        filt="g",
        obj="header label",
    )
    assert image.exists()
    mapping = tmp_path / "objects.csv"
    mapping.write_text("object,horizons_name\nheader label,Vesta\n", encoding="utf-8")

    catalog, _ = catalog_directory(tmp_path, mapping)

    assert catalog.loc[catalog["frame_type"] == "LIGHT", "horizons_name"].iloc[0] == "Vesta"


def test_pipeline_rejects_missing_input_directory(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        run_pipeline(tmp_path / "missing", output_dir=tmp_path / "out", run_horizons=False, run_astap=False)
