"""Per-worker OVOS directory isolation for the end-to-end suite.

Every test class boots its own MiniCroft, which copies the skill's GUI
resources into the shared ``ovos_gui`` cache keyed by skill id. When pytest-xdist
runs several workers in parallel they load the same skill id concurrently and
race on creating that directory, intermittently failing skill load. Giving each
worker its own XDG base dirs removes the shared path and the race.
"""
import os
import tempfile

try:
    import ovoscope  # noqa: F401
except ImportError:
    collect_ignore_glob = ["*.py"]

_worker = os.environ.get("PYTEST_XDIST_WORKER", "gw-single")
_base = os.path.join(tempfile.gettempdir(), f"ovos-date-time-e2e-{_worker}")

for _var, _sub in (
    ("XDG_CACHE_HOME", "cache"),
    ("XDG_CONFIG_HOME", "config"),
    ("XDG_DATA_HOME", "data"),
    ("XDG_STATE_HOME", "state"),
):
    _path = os.path.join(_base, _sub)
    os.makedirs(_path, exist_ok=True)
    os.environ[_var] = _path
