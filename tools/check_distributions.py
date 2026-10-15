"""Install and test each built distribution in isolation from the checkout."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def main() -> None:
    """Validate supplied wheel/sdist files using fresh environments and test copies."""
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python tools/check_distributions.py dist/*")
    tests = Path(__file__).resolve().parents[1] / "tests"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    for key in list(env):
        if key.startswith("SETUPTOOLS_SCM_PRETEND_"):
            env.pop(key)
    for argument in sys.argv[1:]:
        artifact = Path(argument).resolve(strict=True)
        if not (artifact.name.endswith(".whl") or artifact.name.endswith(".tar.gz")):
            raise SystemExit(f"Unexpected distribution: {artifact}")
        with tempfile.TemporaryDirectory(prefix="arcsatisfied-dist-") as temporary:
            root = Path(temporary)
            venv.EnvBuilder(with_pip=True).create(root / "env")
            python = root / "env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            shutil.copytree(tests, root / "tests", ignore=shutil.ignore_patterns("__pycache__"))
            subprocess.run(
                [str(python), "-m", "pip", "install", "--no-cache-dir", f"{artifact}[test]"],
                cwd=root,
                env=env,
                check=True,
            )
            subprocess.run(
                [str(python), "-c", "import arcsatisfied; print(arcsatisfied.__file__)"],
                cwd=root,
                env=env,
                check=True,
            )
            subprocess.run([str(python), "-m", "pytest", "-q", "tests"], cwd=root, env=env, check=True)
            print(f"Validated {artifact.name}", flush=True)


if __name__ == "__main__":
    main()
