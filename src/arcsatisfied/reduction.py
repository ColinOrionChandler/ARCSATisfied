from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from astropy.io import fits
from astropy.stats import sigma_clip


@dataclass(frozen=True)
class CalibrationProducts:
    bias_path: Path | None
    dark_rate_path: Path | None
    flat_paths: dict[str, Path]


@dataclass(frozen=True)
class ReductionResult:
    source_filename: str
    reduced_path: Path | None
    status: str
    error: str = ""


def safe_token(value: Any) -> str:
    text = str(value).strip() or "unknown"
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)


def read_data_header(path: str | Path) -> tuple[np.ndarray, fits.Header]:
    with fits.open(path, memmap=False, ignore_missing_end=True) as hdul:
        hdul.verify("fix")
        for hdu in hdul:
            if hdu.data is not None and getattr(hdu.data, "ndim", 0) >= 2:
                return np.asarray(hdu.data, dtype=np.float32), hdu.header.copy()
    raise ValueError(f"No 2-D image data found in {path}")


def _median_sigma_stack(arrays: list[np.ndarray]) -> np.ndarray:
    if not arrays:
        raise ValueError("Cannot combine an empty image list")
    clipped = sigma_clip(np.stack(arrays, axis=0), sigma=3, cenfunc="median", axis=0)
    return np.ma.median(clipped, axis=0).filled(np.nan).astype(np.float32)


def _write_primary(path: Path, data: np.ndarray, header: fits.Header, overwrite: bool) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    out_header = header.copy()
    for key in ("BLANK", "BZERO", "BSCALE"):
        out_header.pop(key, None)
    fits.PrimaryHDU(data=np.asarray(data, dtype=np.float32), header=out_header).writeto(
        path,
        overwrite=overwrite,
        checksum=True,
    )
    return path


def _rows(frame: pd.DataFrame, frame_type: str) -> pd.DataFrame:
    return frame[frame["frame_type"].astype(str).str.upper() == frame_type].copy()


def build_calibrations(catalog: pd.DataFrame, cals_dir: str | Path, overwrite: bool = False) -> CalibrationProducts:
    cals_root = Path(cals_dir)
    bias_rows = _rows(catalog, "BIAS")
    dark_rows = _rows(catalog, "DARK")
    flat_rows = _rows(catalog, "FLAT")

    bias_path: Path | None = None
    if not bias_rows.empty:
        bias_path = cals_root / "master_bias.fits"
        if overwrite or not bias_path.exists():
            arrays = [read_data_header(path)[0] for path in bias_rows["filepath"]]
            header = fits.Header()
            header["ARCSATRD"] = (True, "Processed by ARCSATisfied")
            header["CALTYPE"] = "BIAS"
            header["NCOMBINE"] = len(arrays)
            _write_primary(bias_path, _median_sigma_stack(arrays), header, True)

    dark_path: Path | None = None
    if not dark_rows.empty:
        dark_path = cals_root / "master_dark_rate.fits"
        if overwrite or not dark_path.exists():
            bias = fits.getdata(bias_path).astype(np.float32) if bias_path is not None else 0.0
            rates: list[np.ndarray] = []
            for path in dark_rows["filepath"]:
                data, header = read_data_header(path)
                exptime = float(header.get("EXPTIME", header.get("EXPOSURE", 0)) or 0)
                if exptime <= 0:
                    raise ValueError(f"Dark frame has non-positive exposure: {path}")
                rates.append((data - bias) / exptime)
            header = fits.Header()
            header["ARCSATRD"] = (True, "Processed by ARCSATisfied")
            header["CALTYPE"] = "DARK_RATE"
            header["EXPTIME"] = 1.0
            header["NCOMBINE"] = len(rates)
            if bias_path is not None:
                header["BIASREF"] = bias_path.name
            _write_primary(dark_path, _median_sigma_stack(rates), header, True)

    flat_paths: dict[str, Path] = {}
    if not flat_rows.empty:
        bias = fits.getdata(bias_path).astype(np.float32) if bias_path is not None else 0.0
        dark = fits.getdata(dark_path).astype(np.float32) if dark_path is not None else 0.0
        for filt, rows in flat_rows.groupby(flat_rows["filter"].fillna("").astype(str)):
            token = safe_token(filt)
            flat_path = cals_root / f"master_flat_{token}.fits"
            flat_paths[str(filt)] = flat_path
            if flat_path.exists() and not overwrite:
                continue
            normalized: list[np.ndarray] = []
            for path in rows["filepath"]:
                data, header = read_data_header(path)
                exptime = float(header.get("EXPTIME", header.get("EXPOSURE", 0)) or 0)
                corrected = data - bias - dark * exptime
                finite = corrected[np.isfinite(corrected)]
                if finite.size == 0:
                    continue
                norm = float(np.nanmedian(finite))
                if not np.isfinite(norm) or norm == 0:
                    continue
                normalized.append(corrected / norm)
            if not normalized:
                raise ValueError(f"No usable flat frames for filter {filt!r}")
            header = fits.Header()
            header["ARCSATRD"] = (True, "Processed by ARCSATisfied")
            header["CALTYPE"] = "FLAT"
            header["FILTER"] = str(filt)
            header["NCOMBINE"] = len(normalized)
            if bias_path is not None:
                header["BIASREF"] = bias_path.name
            if dark_path is not None:
                header["DARKREF"] = dark_path.name
            _write_primary(flat_path, _median_sigma_stack(normalized), header, True)

    return CalibrationProducts(bias_path=bias_path, dark_rate_path=dark_path, flat_paths=flat_paths)


def reduce_science_frames(
    catalog: pd.DataFrame,
    products: CalibrationProducts,
    data_dir: str | Path,
    overwrite: bool = False,
    cosmic_rays: bool = True,
) -> list[ReductionResult]:
    data_root = Path(data_dir)
    science = _rows(catalog, "LIGHT")
    results: list[ReductionResult] = []
    bias = fits.getdata(products.bias_path).astype(np.float32) if products.bias_path is not None else 0.0
    dark = (
        fits.getdata(products.dark_rate_path).astype(np.float32)
        if products.dark_rate_path is not None
        else 0.0
    )

    detect_cosmics = None
    if cosmic_rays:
        from astroscrappy import detect_cosmics as _detect_cosmics

        detect_cosmics = _detect_cosmics

    for _, row in science.iterrows():
        source = Path(str(row["filepath"]))
        out = data_root / f"{source.stem}_reduced.fits"
        if out.exists() and not overwrite:
            results.append(ReductionResult(source.name, out, "existing"))
            continue
        try:
            data, header = read_data_header(source)
            exptime = float(header.get("EXPTIME", header.get("EXPOSURE", row.get("exptime", 0))) or 0)
            filt = str(row.get("filter", ""))
            flat_path = products.flat_paths.get(filt)
            if flat_path is None:
                raise ValueError(f"No master flat for filter {filt!r}")
            flat = fits.getdata(flat_path).astype(np.float32)
            numerator = data - bias - dark * exptime
            corrected = np.full(numerator.shape, np.nan, dtype=np.float32)
            good_flat = np.isfinite(flat) & (flat != 0)
            with np.errstate(divide="ignore", invalid="ignore"):
                np.divide(numerator, flat, out=corrected, where=good_flat)
            cosmic_mask = None
            if detect_cosmics is not None:
                cosmic_mask, corrected = detect_cosmics(corrected)
                corrected = corrected.astype(np.float32)

            header["ARCSATRD"] = (True, "Processed by ARCSATisfied")
            header["ARCRAW"] = source.name
            if products.bias_path is not None:
                header["ARCBIAS"] = products.bias_path.name
            if products.dark_rate_path is not None:
                header["ARCDARK"] = products.dark_rate_path.name
            header["ARCFLAT"] = flat_path.name
            header["ARCCR"] = (bool(detect_cosmics is not None), "Cosmic-ray cleaning attempted")
            header.add_history("Reduced by ARCSATisfied quick reducer.")
            out.parent.mkdir(parents=True, exist_ok=True)
            primary = fits.PrimaryHDU(data=corrected, header=header)
            hdus: list[fits.ImageHDU | fits.PrimaryHDU] = [primary]
            if cosmic_mask is not None:
                hdus.append(fits.ImageHDU(data=cosmic_mask.astype(np.uint8), name="COSMICRAY_MASK"))
            fits.HDUList(hdus).writeto(out, overwrite=True, checksum=True)
            results.append(ReductionResult(source.name, out, "ok"))
        except Exception as exc:
            results.append(ReductionResult(source.name, None, "error", str(exc).replace("\n", " ")))
    return results
