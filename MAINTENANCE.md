# Dependency maintenance

`Anki-TTS-Flet/requirements.txt` pins every direct production dependency for
Windows. Install it directly; CI installs the same file through
`requirements-ci.txt`. Transitive dependencies remain resolved by pip, so a
release build must retain its generated environment or dependency report.

The project requires Python 3.10 or newer. Pillow 12.3.0 supplies the current
security baseline and requires Python 3.10+, so Python 3.9 is no longer a
supported runtime.

Flet and flet-desktop remain pinned to 0.28.3. A current Flet release requires
a separate UI/runtime migration and validation pass; do not upgrade them as a
routine dependency refresh. Dependabot can propose updates, but changes to
these two packages should be evaluated together.
