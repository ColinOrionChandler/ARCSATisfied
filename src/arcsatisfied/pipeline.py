from __future__ import annotations

import json
import csv
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from .astap import run_astap_on_files
from .catalog import catalog_directory, write_catalog
from .horizons import DEFAULT_SITE_CODE, query_horizons_for_catalog, write_horizons_outputs
from .reduction import build_calibrations, reduce_science_frames


def _default_output_dir(input_dir: str | Path) -> Path:
    return Path(input_dir).expanduser().resolve() / "reduced"


def _apply_reduction_results(catalog: pd.DataFrame, results: list[Any]) -> pd.DataFrame:
    updated = catalog.copy()
    for result in results:
        mask = updated["filename"] == result.source_filename
        updated.loc[mask, "reduction_status"] = result.status
        updated.loc[mask, "reduction_error"] = result.error
        updated.loc[mask, "reduced_path"] = str(result.reduced_path or "")
    return updated


def _apply_astap_results(catalog: pd.DataFrame, results: list[Any]) -> pd.DataFrame:
    updated = catalog.copy()
    for result in results:
        mask = updated["reduced_path"].astype(str).map(lambda value: Path(value).name if value else "") == result.source_filename
        updated.loc[mask, "astap_status"] = result.status
        updated.loc[mask, "astap_error"] = result.error
    return updated


def _apply_horizons_status(catalog: pd.DataFrame, results: pd.DataFrame, failures: pd.DataFrame) -> pd.DataFrame:
    updated = catalog.copy()
    for frame, status in ((results, "ok"), (failures, "error")):
        if frame.empty or "catalog_index" not in frame:
            continue
        for _, row in frame.iterrows():
            index = int(row["catalog_index"])
            if index in updated.index:
                updated.loc[index, "horizons_status"] = status
                updated.loc[index, "horizons_error"] = str(row.get("error", ""))
    science_mask = updated["frame_type"].astype(str).str.upper() == "LIGHT"
    missing_mask = science_mask & updated["horizons_status"].astype(str).str.strip().eq("")
    updated.loc[missing_mask, "horizons_status"] = "skipped"
    updated.loc[missing_mask, "horizons_error"] = "No Horizons name or datetime"
    return updated


def _write_dict_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        if not fieldnames:
            handle.write("")
            return
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_pipeline(
    input_dir: str | Path,
    *,
    output_dir: str | Path | None = None,
    object_map: str | Path | None = None,
    overwrite: bool = False,
    cosmic_rays: bool = True,
    run_horizons: bool = True,
    site_code: str = DEFAULT_SITE_CODE,
    horizons_id_type: str | None = "smallbody",
    run_astap: bool = True,
    astap_path: str | Path | None = None,
    astap_timeout: int = 120,
) -> dict[str, Any]:
    input_root = Path(input_dir).expanduser().resolve()
    if not input_root.is_dir():
        raise NotADirectoryError(f"Input directory does not exist: {input_root}")
    out_root = Path(output_dir).expanduser().resolve() if output_dir else _default_output_dir(input_root)
    data_dir = out_root / "data"
    cals_dir = out_root / "cals"
    catalog_dir = out_root / "catalog"
    logs_dir = out_root / "logs"
    for directory in (data_dir, cals_dir, catalog_dir, logs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    catalog, header_records = catalog_directory(input_root, object_map)
    write_catalog(catalog, header_records, catalog_dir)

    calibrations = build_calibrations(catalog, cals_dir, overwrite=overwrite)
    reduction_results = reduce_science_frames(
        catalog,
        calibrations,
        data_dir,
        overwrite=overwrite,
        cosmic_rays=cosmic_rays,
    )
    _write_dict_rows(logs_dir / "reduction_results.csv", [asdict(result) for result in reduction_results])
    catalog = _apply_reduction_results(catalog, reduction_results)

    reduced_paths = [Path(result.reduced_path) for result in reduction_results if result.reduced_path is not None]
    astap_results = run_astap_on_files(
        reduced_paths,
        astap_path=astap_path,
        timeout=astap_timeout,
        enabled=run_astap,
    )
    _write_dict_rows(logs_dir / "astap_results.csv", [asdict(result) for result in astap_results])
    catalog = _apply_astap_results(catalog, astap_results)

    if run_horizons:
        horizons_outputs = query_horizons_for_catalog(
            catalog,
            site_code=site_code,
            id_type=horizons_id_type,
            cache=False,
        )
    else:
        horizons_outputs = query_horizons_for_catalog(catalog.iloc[0:0], site_code=site_code)
    write_horizons_outputs(horizons_outputs, catalog_dir)
    catalog = _apply_horizons_status(catalog, horizons_outputs.results, horizons_outputs.failures)
    catalog_csv, headers_jsonl = write_catalog(catalog, header_records, catalog_dir)

    summary = {
        "input_dir": str(input_root),
        "output_dir": str(out_root),
        "catalog_csv": str(catalog_csv),
        "headers_jsonl": str(headers_jsonl),
        "fits_count": int(len(catalog)),
        "science_count": int((catalog["frame_type"].astype(str).str.upper() == "LIGHT").sum()),
        "reduced_ok_count": int((catalog["reduction_status"] == "ok").sum()),
        "reduction_error_count": int((catalog["reduction_status"] == "error").sum()),
        "horizons_ok_count": int((catalog["horizons_status"] == "ok").sum()),
        "horizons_error_count": int((catalog["horizons_status"] == "error").sum()),
        "astap_ok_count": int((catalog["astap_status"] == "ok").sum()),
        "astap_error_count": int((catalog["astap_status"] == "error").sum()),
        "calibrations": {
            "bias_path": str(calibrations.bias_path or ""),
            "dark_rate_path": str(calibrations.dark_rate_path or ""),
            "flat_paths": {key: str(value) for key, value in calibrations.flat_paths.items()},
        },
        "astap_results": [asdict(result) for result in astap_results],
    }
    summary_path = logs_dir / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
