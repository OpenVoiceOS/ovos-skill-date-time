# How the skill speaks the time and the date
<!-- agent-hint
covers: which writer speaks each slot (time, date, weekday, month, year, days until), the chronologia reader, the writer for each locale
source: speech.py, __init__.py (get_spoken_time, handle_query_date, handle_weekday, handle_current_day), test/end2end/spoken_pin_rows.py
generated: no
verify: (for f in nice_weekday nice_month nice_duration nice_day; do grep -q "^| \`$f\`" docs/speech.md || { echo "page lacks $f"; exit 1; }; grep -q "$f(" __init__.py || { echo "code lacks $f"; exit 1; }; done; for f in spoken_time spoken_date spoken_day_month spoken_year; do grep -q "^| \`$f\`" docs/speech.md || { echo "page lacks $f"; exit 1; }; grep -q "def $f(" speech.py || { echo "speech.py lacks $f"; exit 1; }; done; grep -q "is None and writes(lang)" speech.py || { echo "relative date path differs"; exit 1; }; grep -q "from chronologia import extract_candidates, extract_duration, extract_timespan" __init__.py || { echo "chronologia import changed"; exit 1; }; grep -q "datetime.datetime(2026, 3, 4, 14, 35)" test/end2end/test_spoken_writers.py || { echo "anchor changed"; exit 1; }; echo OK)
see: settings.md, testing.md
-->

The skill reads the date in a request with chronologia. It writes the time, the date and the year with the functions in `speech.py`, and each other spoken value with an `ovos_date_parser.nice_*` function. With the clock frozen at Wednesday 4 March 2026, 14:35, Europe/Lisbon, and a 12-hour session, the en-US skill fills the slots like this:

```text
"what time is it"                          -> time     = two thirty five p.m.
"what's the date today"                    -> date     = wednesday, march fourth, twenty twenty six
"what day of the week is it"               -> weekday  = wednesday
"what day of the week is march twentieth"  -> weekday  = friday
"what month is it"                         -> month    = march
"what year is it"                          -> year     = twenty twenty six
"how many days until march twentieth"      -> num_days = sixteen days
```

`test/end2end/test_spoken_writers.py` checks these rows and the same rows in pt-PT, pt-BR, es-ES, fr-FR, it-IT, de-DE, nl-NL and da-DK.

## The writer for each slot

| Function | Slot | Dialog |
| :--- | :--- | :--- |
| `spoken_time` | `{time}` | `time_current`, `time_future` |
| `spoken_date` | `{date}`, `{from_date}`, `{to_date}` | `date`, `date_relative_future`, `date_relative_past`, `days_between`, the weekday dialogs |
| `spoken_day_month` | `{saturday_date}`, `{sunday_date}` | `date_future_weekend`, `date_last_weekend` |
| `nice_weekday` | `{weekday}` | `weekday_current`, `weekday_at_date_future`, `weekday_at_date_past` |
| `nice_month` | `{month}` | `month_current` |
| `spoken_year` | `{year}` | `year_current` |
| `nice_duration` | `{num_days}` | `date_relative_future`, `date_relative_past`, `days_between` |
| `nice_day` | `{day}` | `day_current` |

`handle_current_day` uses `spoken_date`. When `nice_date` has no date format for the language, it raises `KeyError` or `NotImplementedError`, and the skill speaks `day_current` with `nice_day`.

`spoken_day_month` gives the weekday, the day and the month with no year. The `nice_date` fallback keeps the first two parts of the `nice_date` text, split at ", ".

## The time

`get_spoken_time` calls `spoken_time`. The session `time_format` selects the clock (see [settings.md](settings.md)):

| `time_format` | Spoken | Shown |
| :--- | :--- | :--- |
| `full` | fourteen thirty five | 14:35 |
| any other value | two thirty five p.m. | 2:35 PM |

In the 12-hour form, the skill replaces "AM" with "A.M." in the spoken text.

## The reader

The skill imports `extract_candidates`, `extract_duration` and `extract_timespan` from chronologia. They find the date or the length of time in a request ("in two hours", "march twentieth"). 

## The writer for each locale

`spoken_time`, `spoken_date`, `spoken_day_month` and `spoken_year` call the chronologia writer when `chronologia.spoken.writes(lang)` is true. chronologia writes pt-PT. For each other locale, and when chronologia raises `UnsupportedForm`, they call `nice_time`, `nice_date` or `nice_year`.

A date with a reference day always goes to `nice_date`. chronologia has no relative words, so only `nice_date` says "today" or "tomorrow" and drops the year that the date shares with the reference day. Each day count (`{num_days}`) uses `nice_duration`, because chronologia writes no lengths of time.

The 12- or 24-hour clock comes from the session `time_format`. In pt-PT, the 12-hour clock gives the conversational reading ("três menos vinte e cinco da tarde"), and the 24-hour clock gives the digits reading ("catorze e trinta e cinco").

A locale moves to the chronologia writer only when chronologia writes that locale and the rows of that locale in `test_spoken_writers.py` pass with it. A locale that ovos-date-parser writes incorrectly keeps a strict xfail row until the fix (see [testing.md](testing.md)).

---
[← Prev](usage.md) · [Home](index.md) · [Next →](settings.md)
