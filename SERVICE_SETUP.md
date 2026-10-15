# Service setup and releases

## Read the Docs

Import `ColinOrionChandler/ARCSATisfied` into the owner's Read the Docs Community
account with slug `arcsatisfied`. Use `main` as the default branch and enable
pull-request builds. The repository's `.readthedocs.yml` installs the package and
builds Sphinx on Python 3.12 with warnings treated as errors. Confirm the hosted
installation, usage, and API pages after the first successful build.

## Codecov

Enable this repository in the owner's Codecov GitHub account. The Linux 3.12
workflow uploads `coverage.xml` using GitHub OIDC (`id-token: write`), so no
long-lived upload token is stored. Verify the report is associated with the
actual commit SHA. Coverage is reported without percentage gates or PR comments.

## PyPI Trusted Publishing

Configure a pending GitHub publisher in the owner's PyPI account:

| Field | Value |
| --- | --- |
| PyPI project | `arcsatisfied` |
| GitHub owner | `ColinOrionChandler` |
| Repository | `ARCSATisfied` |
| Workflow filename | `publish-to-pypi.yml` |
| GitHub environment | `pypi` |

Create the matching GitHub environment. A pending publisher does not create a
PyPI project or reserve its name. Package publication remains untested until the
first release. This migration does not publish packages or create release tags.

## Future release procedure

After an explicit release request, verify CI on the chosen main commit and
recheck PyPI name ownership. Tag that commit `v0.1.0` for the first release and
publish its GitHub release. The release-only workflow builds wheel and source
distribution, validates metadata, installs and tests both in fresh environments,
and then publishes using OIDC. Inspect the completed workflow and verify a clean
installation from PyPI, both CLI entry points, and the reported version.

Do not move an existing published tag or retry an upload with different content
under the same version. Fixes require a new version.

## Migration verification status

As of 2026-10-14:

- GitHub environment `pypi`: created and verified through the GitHub API.
- Read the Docs: repository configuration is ready; GitHub/Read the Docs account
  sign-in is required to import the project and verify hosted builds.
- PyPI: release workflow is ready; account sign-in is required to save the pending
  publisher. No PyPI publisher has yet been saved, and no package was uploaded.
- Codecov: the GitHub CI test step passes, but the OIDC upload is rejected with
  `Repository not found`. Sign in to Codecov with GitHub, enable this repository,
  and rerun the failed job to verify the coverage report before merging.
- Local verification: 11 tests pass; wheel and sdist each pass all 11 tests in
  fresh environments outside the checkout; strict Twine and pre-commit pass.
- GitHub verification: test steps pass on all five Linux Python versions and
  macOS 3.12; distribution, documentation, and lint jobs pass. The Linux 3.12
  job remains red solely because the subsequent Codecov upload is rejected.

Keep the migration PR open until the remaining service setup is verified; do not
represent configuration files as evidence of a successful hosted deployment.
