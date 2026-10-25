# Dependency maintenance

`Anki-TTS-Flet/requirements.txt` pins every direct production dependency for
Windows. Install it directly; CI installs the same file through
`requirements-ci.txt`. Transitive dependencies remain resolved by pip, so a
release build must retain its generated environment or dependency report.

Source runs require Python 3.11 or newer. Pillow 13.0.0 is the security
baseline and requires Python 3.11+. Pillow is used only for the built-in tray
icon. Do not add a Python 3.10 conditional downgrade to an older Pillow version.
The Windows release package includes its Python interpreter. Security upgrades
still require CI and packaged-build validation before release.

Flet and flet-desktop remain pinned to 0.28.3. A current Flet release requires
a separate UI/runtime migration and validation pass; do not upgrade them as a
routine dependency refresh. Dependabot can propose updates, but changes to
these two packages should be evaluated together.
