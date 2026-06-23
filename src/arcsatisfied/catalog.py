from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from astropy.io import fits
from astropy.time import Time, TimeDelta


FITS_SUFFIXES = (".fits", ".fit", ".fts", ".fits.fz", ".fit.fz")
DEFAULT_IGNORE_DIRS = {".git", "__pycache__", ".pytest_cache", "reduced"}
OBJECT_KEYS = ("OBJECT", "OBJNAME", "OBJCTNAM", "OBJCTNAME", "TARGET", "TARGNAME")

CATALOG_COLUMNS = [
    "filepath",
    "filename",
    "frame_type",
    "datetime",
    "mjd_mid",
    "exptime",
    "filter",
    "object",
    "horizons_name",
    "ra",
    "dec",
    "objctra",
    "objctdec",
    "airmass",
    "azimuth",
    "elevat",
    "instrume",
    "telescop",
    "observer",
    "xbinning",
    "ybinning",
    "ccdsum",
    "binning",
    "naxis1",
    "naxis2",
    "wcs_status",
    "reduced_path",
    "reduction_status",
    "reduction_error",
    "astap_status",
    "astap_error",
    "horizons_status",
    "horizons_error",
]


@dataclass(frozen=True)
class HeaderRecord:
    row: dict[str, Any]
    header_record: dict[str, Any]


def discover_fits(input_dir: str | Path, ignore_dirs: set[str] | None = None) -> list[Path]:
    root = Path(input_dir).expanduser().resolve()
    ignored = {part.lower() for part in (ignore_dirs or DEFAULT_IGNORE_DIRS)}
    paths: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or not path.name.lower().endswith(FITS_SUFFIXES):
            continue
        rel_parts = {part.lower() for part in path.relative_to(root).parts[:-1]}
        if rel_parts & ignored:
            continue
        paths.append(path.resolve())
    return sorted(paths, key=lambda item: str(item))


def text_value(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    return str(value).strip()


def json_safe_value(value: Any) -> Any:
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return str(value)


def first_header_text(header: fits.Header, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = text_value(header.get(key))
        if value:
            return value
    return ""


def normalize_frame_type(header: fits.Header) -> str:
    raw = first_header_text(header, ("IMAGETYP", "IMAGTYPE", "DATA-TYP")).upper()
    if raw in {"BIAS", "ZERO"}:
        return "BIAS"
    if raw == "DARK":
        return "DARK"
    if raw in {"FLAT", "DOMEFLAT", "SKYFLAT"}:
        return "FLAT"
    if raw in {"LIGHT", "OBJECT", "SCIENCE"}:
        return "LIGHT"
    return raw or "UNKNOWN"


def parse_start_time(header: fits.Header) -> Time | None:
    date_obs = text_value(header.get("DATE-OBS"))
    time_obs = text_value(header.get("TIME-OBS") or header.get("UT"))
    candidates = []
    if date_obs:
        candidates.append(date_obs)
        if "T" not in date_obs and time_obs:
            candidates.insert(0, f"{date_obs}T{time_obs}")
    for candidate in candidates:
        try:
            return Time(candidate, format="isot", scale="utc")
        except Exception:
            try:
                return Time(candidate, scale="utc")
            except Exception:
                continue
    return None


def midpoint_values(header: fits.Header) -> tuple[str, str]:
    start = parse_start_time(header)
    if start is None:
        return "", ""
    exptime = float(header.get("EXPTIME", header.get("EXPOSURE", 0)) or 0)
    midpoint = start + TimeDelta(exptime / 2.0, format="sec")
    return midpoint.utc.isot, f"{midpoint.utc.mjd:.9f}"


def binning_value(header: fits.Header) -> str:
    ccdsum = text_value(header.get("CCDSUM"))
    if ccdsum:
        parts = [part for part in re.split(r"[xX,\s]+", ccdsum) if part]
        if len(parts) >= 2 and all(part.lstrip("+-").isdigit() for part in parts[:2]):
            return f"{int(parts[0])}x{int(parts[1])}"
        return ccdsum
    xbin = text_value(header.get("XBINNING"))
    ybin = text_value(header.get("YBINNING"))
    if xbin and ybin:
        return f"{xbin}x{ybin}"
    return ""


def load_object_map(path: str | Path | None) -> dict[str, str]:
    if path is None:
        return {}
    mapping_path = Path(path).expanduser()
    if not mapping_path.exists():
        raise FileNotFoundError(f"Object map does not exist: {mapping_path}")
    with mapping_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    mapping: dict[str, str] = {}
    for row in rows:
        target = (
            row.get("horizons_name")
            or row.get("target")
            or row.get("query_name")
            or row.get("jpl_name")
            or ""
        ).strip()
        if not target:
            continue
        for key in ("filename", "object", "source_object", "header_object", "pattern"):
            value = (row.get(key) or "").strip()
            if value:
                mapping[value.casefold()] = target
    return mapping


def infer_horizons_name(path: Path, header_object: str, object_map: dict[str, str] | None = None) -> str:
    object_map = object_map or {}
    if path.name.casefold() in object_map:
        return object_map[path.name.casefold()]
    if header_object.casefold() in object_map:
        return object_map[header_object.casefold()]

    if header_object:
        return header_object.strip()

    stem = path.stem
    match = re.match(r"(?P<name>[A-Za-z][A-Za-z0-9+\-. ]*?)_[A-Za-z]+_\d{8}_\d{6}$", stem)
    if match:
        return match.group("name").strip()
    return ""


def read_image_header(path: str | Path) -> fits.Header:
    with fits.open(path, memmap=False, ignore_missing_end=True) as hdul:
        hdul.verify("fix")
        for hdu in hdul:
            if hdu.data is not None and getattr(hdu.data, "ndim", 0) >= 2:
                return hdu.header.copy()
        return hdul[0].header.copy()


def catalog_record(path: str | Path, object_map: dict[str, str] | None = None) -> HeaderRecord:
    filepath = Path(path).expanduser().resolve()
    row = {column: "" for column in CATALOG_COLUMNS}
    row["filepath"] = str(filepath)
    row["filename"] = filepath.name

    header_record = {
        "filepath": str(filepath),
        "filename": filepath.name,
        "read_status": "ok",
        "read_error": "",
        "header_cards": [],
    }
    try:
        header = read_image_header(filepath)
        frame_type = normalize_frame_type(header)
        midpoint_iso, mjd_mid = midpoint_values(header)
        header_object = first_header_text(header, OBJECT_KEYS)
        row.update(
            {
                "frame_type": frame_type,
                "datetime": midpoint_iso,
                "mjd_mid": mjd_mid,
                "exptime": text_value(header.get("EXPTIME", header.get("EXPOSURE"))),
                "filter": text_value(header.get("FILTER")),
                "object": header_object,
                "horizons_name": infer_horizons_name(filepath, header_object, object_map)
                if frame_type == "LIGHT"
                else "",
                "ra": text_value(header.get("RA")),
                "dec": text_value(header.get("DEC")),
                "objctra": text_value(header.get("OBJCTRA")),
                "objctdec": text_value(header.get("OBJCTDEC")),
                "airmass": text_value(header.get("AIRMASS")),
                "azimuth": text_value(header.get("AZIMUTH")),
                "elevat": text_value(header.get("ELEVAT")),
                "instrume": text_value(header.get("INSTRUME")),
                "telescop": text_value(header.get("TELESCOP")),
                "observer": text_value(header.get("OBSERVER")),
                "xbinning": text_value(header.get("XBINNING")),
                "ybinning": text_value(header.get("YBINNING")),
                "ccdsum": text_value(header.get("CCDSUM")),
                "binning": binning_value(header),
                "naxis1": text_value(header.get("NAXIS1")),
                "naxis2": text_value(header.get("NAXIS2")),
                "wcs_status": "present" if header.get("CTYPE1") and header.get("CTYPE2") else "none",
            }
        )
        header_record["header_cards"] = [
            {
                "key": card.keyword,
                "value": json_safe_value(card.value),
                "comment": text_value(card.comment),
            }
            for card in header.cards
        ]
    except Exception as exc:
        error = str(exc).replace("\n", " ").strip()
        row["frame_type"] = "ERROR"
        row["reduction_status"] = "read_error"
        row["reduction_error"] = error
        header_record["read_status"] = "error"
        header_record["read_error"] = error

    return HeaderRecord(row=row, header_record=header_record)


def catalog_directory(input_dir: str | Path, object_map_path: str | Path | None = None) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    object_map = load_object_map(object_map_path)
    records = [catalog_record(path, object_map) for path in discover_fits(input_dir)]
    rows = [record.row for record in records]
    headers = [record.header_record for record in records]
    return pd.DataFrame(rows, columns=CATALOG_COLUMNS), headers


def write_catalog(frame: pd.DataFrame, header_records: list[dict[str, Any]], catalog_dir: str | Path) -> tuple[Path, Path]:
    catalog_path = Path(catalog_dir)
    catalog_path.mkdir(parents=True, exist_ok=True)
    csv_path = catalog_path / "arcsat_catalog.csv"
    jsonl_path = catalog_path / "fits_headers.jsonl"
    frame.to_csv(csv_path, index=False)
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in header_records:
            json.dump(record, handle, ensure_ascii=False)
            handle.write("\n")
    return csv_path, jsonl_path


def science_rows(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["frame_type"].astype(str).str.upper() == "LIGHT"].copy()
