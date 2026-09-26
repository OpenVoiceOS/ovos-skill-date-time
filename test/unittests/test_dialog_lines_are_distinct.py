"""Every .dialog file must offer distinct lines.

A .dialog file is a list of alternatives, and the renderer picks one at
random. A line that appears twice is not a second alternative: it doubles
its own chance and it silently costs the locale a variant that the
reference locale does have. en-US keeps "It's {day} today" apart from
"Today is {day}"; a locale that renders both as one sentence and ships it
twice answers with less variety than the skill was written to have.

A placeholder-parity check cannot see this, because a repeated line
repeats its placeholders too. So this guard reads the lines themselves.

The 14 files that ovos-skill-date-time#350 added with a repeated line
(cs-CZ, fa-IR, hu-HU, pl-PL, ru-RU and tr-TR day_current,
weekday_current and month_current) are the reason this test exists.
"""
import collections
from pathlib import Path

import pytest

LOCALE = Path(__file__).parent.parent.parent / "locale"

DIALOGS = sorted(LOCALE.glob("*/dialog/*.dialog"))


def _lines(path):
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def test_the_locale_tree_is_readable():
    """A guard over an empty list passes for the wrong reason."""
    assert len(DIALOGS) > 100, f"only {len(DIALOGS)} dialog files found under {LOCALE}"


@pytest.mark.parametrize("path", DIALOGS, ids=lambda p: f"{p.parent.parent.name}/{p.name}")
def test_every_line_of_a_dialog_file_is_distinct(path):
    lines = _lines(path)
    repeated = {line: n for line, n in collections.Counter(lines).items() if n > 1}
    assert not repeated, (
        f"{path.parent.parent.name}/{path.name} repeats "
        f"{len(repeated)} line(s), so it offers {len(set(lines))} alternatives "
        f"and not {len(lines)}: "
        + "; ".join(f"{line!r} x{n}" for line, n in sorted(repeated.items()))
    )
