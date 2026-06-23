from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from astropy.time import Time


DEFAULT_SITE_CODE = "705"
HORIZONS_MAX_EPOCHS_PER_QUERY = 10


@dataclass(frozen=True)
class HorizonsOutputs:
    results: pd.DataFrame
    failures: pd.DataFrame


def _chunked(values: list[Any], size: int) -> list[list[Any]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def query_horizons_for_catalog(
    catalog: pd.DataFrame,
    *,
    site_code: str = DEFAULT_SITE_CODE,
    id_type: str | None = "smallbody",
    max_epochs: int = HORIZONS_MAX_EPOCHS_PER_QUERY,
    horizons_cls: Callable[..., Any] | None = None,
    cache: bool = False,
) -> HorizonsOutputs:
    if horizons_cls is None:
        from astroquery.jplhorizons import Horizons

        horizons_cls = Horizons

    science = catalog[catalog["frame_type"].astype(str).str.upper() == "LIGHT"].copy()
    science = science[
        science["horizons_name"].astype(str).str.strip().ne("")
        & science["datetime"].astype(str).str.strip().ne("")
    ].copy()

    result_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    query_size = min(max(1, int(max_epochs)), HORIZONS_MAX_EPOCHS_PER_QUERY)

    for object_name, group in science.groupby(science["horizons_name"].astype(str)):
        epoch_rows: list[tuple[float, list[str], list[int], list[str]]] = []
        for datetime_value, time_group in group.groupby(group["datetime"].astype(str)):
            try:
                jd = float(Time(datetime_value, scale="utc").jd)
            except Exception as exc:
                for index, row in time_group.iterrows():
                    failure_rows.append(
                        {
                            "source_filename": row["filename"],
                            "catalog_index": index,
                            "horizons_name": object_name,
                            "query_epoch_utc": datetime_value,
                            "site_code": site_code,
                            "query_status": "error",
                            "error": f"invalid datetime: {exc}",
                        }
                    )
                continue
            epoch_rows.append(
                (
                    jd,
                    time_group["filename"].astype(str).tolist(),
                    [int(index) for index in time_group.index.tolist()],
                    [datetime_value] * len(time_group),
                )
            )

        epoch_rows.sort(key=lambda item: item[0])
        for chunk in _chunked(epoch_rows, query_size):
            jd_epochs = [item[0] for item in chunk]
            try:
                table = horizons_cls(
                    id=object_name,
                    location=site_code,
                    epochs=jd_epochs,
                    id_type=id_type,
                ).ephemerides(cache=cache)
                frame = table.to_pandas()
                if frame.empty:
                    raise RuntimeError("Horizons returned no rows")
                for chunk_index, (_, filenames, catalog_indices, datetime_values) in enumerate(chunk):
                    if chunk_index >= len(frame):
                        raise RuntimeError("Horizons returned fewer rows than requested epochs")
                    values = frame.iloc[chunk_index].to_dict()
                    for filename, catalog_index, datetime_value in zip(
                        filenames,
                        catalog_indices,
                        datetime_values,
                    ):
                        result_rows.append(
                            {
                                "source_filename": filename,
                                "catalog_index": catalog_index,
                                "horizons_name": object_name,
                                "query_epoch_utc": datetime_value,
                                "site_code": site_code,
                                "query_status": "ok",
                                "error": "",
                                **values,
                            }
                        )
            except Exception as exc:
                error = str(exc).replace("\n", " ").strip()
                for _, filenames, catalog_indices, datetime_values in chunk:
                    for filename, catalog_index, datetime_value in zip(
                        filenames,
                        catalog_indices,
                        datetime_values,
                    ):
                        failure_rows.append(
                            {
                                "source_filename": filename,
                                "catalog_index": catalog_index,
                                "horizons_name": object_name,
                                "query_epoch_utc": datetime_value,
                                "site_code": site_code,
                                "query_status": "error",
                                "error": error,
                            }
                        )

    return HorizonsOutputs(pd.DataFrame(result_rows), pd.DataFrame(failure_rows))


def write_horizons_outputs(outputs: HorizonsOutputs, catalog_dir: str | Path) -> tuple[Path, Path]:
    root = Path(catalog_dir)
    root.mkdir(parents=True, exist_ok=True)
    results_path = root / "horizons_catalog.csv"
    failures_path = root / "horizons_failures.csv"
    outputs.results.to_csv(results_path, index=False)
    outputs.failures.to_csv(failures_path, index=False)
    return results_path, failures_path
