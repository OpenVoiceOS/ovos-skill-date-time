"""The ODbL attribution has to travel with the distribution.

The skill queries the timezone boundary database that `timezonefinder-data`
installs under the Open Database License v1.0, and the ODbL asks for
attribution wherever the data goes. A credit that lives only in repository
prose does not reach someone who installed the wheel, so the notice ships:
`license-files` puts it in the wheel's `dist-info/licenses/` and names it in
the metadata, and `MANIFEST.in` puts it in the sdist.
"""
try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
NOTICE = ROOT / "NOTICE"


def test_the_notice_credits_the_data_and_its_terms():
    text = NOTICE.read_text(encoding="utf-8")
    for credit in ("timezonefinder-data", "timezone-boundary-builder",
                   "OpenStreetMap", "Open Database License (ODbL) v1.0",
                   "share-alike"):
        assert credit in text, f"NOTICE does not name {credit!r}"


def test_the_notice_ships_in_the_wheel():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    license_files = pyproject["tool"]["setuptools"]["license-files"]
    assert "NOTICE" in license_files, (
        "NOTICE is not declared in license-files, so the wheel carries the "
        "attribution nowhere")


def test_the_notice_ships_in_the_sdist():
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8").split("\n")
    assert "include NOTICE" in manifest, "NOTICE is not included in the sdist"
