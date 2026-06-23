from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from astropy.io import fits


ASTAP_CANDIDATES = (
    "/Applications/ASTAP.app/Contents/MacOS/astap",
    "/Users/colinchandler/Colinchandler Dropbox/Colin Chandler/bin/astap",
)


@dataclass(frozen=True)
class AstapResult:
    source_filename: str
    status: str
    error: str = ""
    command: str = ""


def find_astap(explicit: str | Path | None = None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.exists() else None
    on_path = shutil.which("astap")
    if on_path:
        return Path(on_path)
    for candidate in ASTAP_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            return path
    return None


def has_pointing_metadata(path: str | Path) -> bool:
    try:
        header = fits.getheader(path)
    except Exception:
        return False
    return bool(
        (header.get("RA") and header.get("DEC"))
        or (header.get("OBJCTRA") and header.get("OBJCTDEC"))
    )


def run_astap_on_files(
    paths: list[Path],
    *,
    astap_path: str | Path | None = None,
    timeout: int = 120,
    enabled: bool = True,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> list[AstapResult]:
    if not enabled:
        return [AstapResult(path.name, "skipped", "ASTAP disabled") for path in paths]
    executable = find_astap(astap_path)
    if executable is None:
        return [AstapResult(path.name, "missing", "ASTAP executable not found") for path in paths]
    runner = runner or subprocess.run
    results: list[AstapResult] = []
    for path in paths:
        if not has_pointing_metadata(path):
            results.append(AstapResult(path.name, "skipped", "No RA/Dec pointing metadata"))
            continue
        command = [str(executable), "-f", str(path), "-r", "30"]
        try:
            completed = runner(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if completed.returncode == 0:
                results.append(AstapResult(path.name, "ok", "", " ".join(command)))
            else:
                stderr = (completed.stderr or completed.stdout or "").replace("\n", " ").strip()
                results.append(
                    AstapResult(
                        path.name,
                        "error",
                        f"exit {completed.returncode}: {stderr}",
                        " ".join(command),
                    )
                )
        except Exception as exc:
            results.append(AstapResult(path.name, "error", str(exc).replace("\n", " "), " ".join(command)))
    return results
