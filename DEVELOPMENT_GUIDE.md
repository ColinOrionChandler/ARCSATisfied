# Developing ARCSATisfied

## Environment and checks

Use Python 3.10+ and a dedicated virtual environment. Install with
`python -m pip install -e '.[dev]'` and install documentation dependencies with
`python -m pip install -r docs/requirements.txt`. Run `pre-commit install` once.
Use feature branches; the pre-commit configuration protects `main` and `master`.

Run `python -m pytest`, `pre-commit run --all-files`, and
`python -m sphinx -W --keep-going -b html docs docs/_build/html` before a PR.
Ruff uses a 110-character line length and Python 3.10 syntax compatibility.
Public functions/classes should have useful docstrings. Test helper docstrings
are optional. Keep the hook and development Ruff versions compatible.

Build with `python -m build`, validate with `python -m twine check --strict dist/*`,
and run `python tools/check_distributions.py dist/*`. That script installs each
artifact into a fresh environment outside the checkout, copies the tests there,
and runs them with `PYTHONPATH` unset. Source distributions build without `.git`.

## Scientific behavior

The `src/arcsatisfied` package separates catalog extraction, calibration/reduction,
Horizons queries, ASTAP integration, and pipeline/CLI orchestration. Preserve raw
FITS pixels, literal object labels, output names, metadata, and provenance.
Use synthetic FITS fixtures for tests; no real observing data belongs in Git.
Mock Horizons and ASTAP in routine tests. Never silently substitute a target
identity or interpret an API/solver failure as a scientific no-match.

## Template provenance and updates

Generated with Copier 9.19.1 from LINCC Python Project Template v2.3.0 using
`.copier-answers.yml`. On a clean feature branch, use Copier 9.1+ and
`copier update --vcs-ref <reviewed-tag>`, inspect all changes and conflicts, and
rerun the checks above. Do not run `.initialize_new_project.sh` in this repository.

Project-specific deviations to preserve when updating:

- Repository/display name is `ARCSATisfied`; distribution/import name is
  `arcsatisfied`. Keep the original `arcsatisfied` and module CLI entry points,
  `[test]` extra, five runtime dependencies, and source/test layout.
- No example modules, extra version CLI, notebooks/Jupyter, benchmarks, mypy,
  lowest-dependency matrix, or custom email/Slack notifications.
- Explicit setuptools >=77.0.3 for SPDX metadata, setuptools-scm >=8, generated
  `_version.py`, and archive substitutions. Never commit the generated version.
  `.git_archival.txt` omits the bare `node` field so an archive without tags uses
  `fallback_version = "0.1.dev0"` instead of upstream's misleading `0.0`.
  Tagged archives still use `describe-name`/`ref-names`; sdists retain their exact
  metadata version. For exact development versions, build from a Git checkout
  or its sdist, since an untagged archive cannot recover commit distance.
- Installed-package tests have no `pythonpath` override. CI tests Linux 3.10–3.14
  and macOS 3.12. Documentation and packaging use 3.12; all build checkouts fetch
  full history and tags. Doctest collection is not enabled for CLI examples.
- Ruff retains template rules with test-only docstring exemptions. Narrow
  SIM105/B905 exemptions preserve the existing catalog and Horizons control flow. Pre-commit's
  pytest hook fails on collection errors. CI runs validation hooks but delegates
  tests to their own job and skips the local branch guard and update notice.
- Coverage uploads use GitHub OIDC on the Linux 3.12 job. Codecov has no coverage
  percentage gates or PR comments. Publication is release-only, uses environment
  `pypi`, and validates wheel/sdist installs before uploading.
- Documentation uses MyST for shared Markdown guides, ignores build output,
  and treats warnings as failures. Service instructions live in `SERVICE_SETUP.md`.

## Versions

`setuptools-scm` derives versions from Git tags, writes the ignored `_version.py`,
and embeds version metadata in source distributions. Install the project before
importing it; a bare uninstalled checkout is not supported. With no release tags,
versions are development versions. The planned first release tag is `v0.1.0`.
