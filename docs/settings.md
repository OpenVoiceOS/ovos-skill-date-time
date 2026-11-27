# Session values and settings
<!-- agent-hint
covers: the 12- and 24-hour session time_format, the date_format of the display, the hourly chime settings
source: __init__.py (use_24hour, get_display_date, play_hour_chime, hour_chime), settingsmeta.json
generated: no
verify: (p=$(grep -o '^| `[a-z]*` | 24-hour' docs/settings.md | cut -d'`' -f2); c=$(grep -o "time_format == '[a-z]*'" __init__.py | cut -d"'" -f2); [ "$p" = "$c" ] || { echo "clock: page $p, code $c"; exit 1; }; p=$(grep -o '`play_hour_chime` | boolean | `[A-Za-z]*`' docs/settings.md | grep -o '`[A-Za-z]*`$' | tr -d '`'); c=$(grep -o '"play_hour_chime", [A-Za-z]*' __init__.py | cut -d' ' -f2 | tr A-Z a-z); [ "$p" = "$c" ] || { echo "chime: page $p, code $c"; exit 1; }; p=$(grep -o '`hour_sound` | string | `[a-z.-]*`' docs/settings.md | grep -o '`[a-z.-]*`$' | tr -d '`'); c=$(grep -o '"hour_sound", "[a-z.-]*"' __init__.py | cut -d'"' -f4); [ "$p" = "$c" ] || { echo "sound: page $p, code $c"; exit 1; }; echo OK)
see: speech.md, timezone.md
-->

The skill reads the clock format and the date format from the session. Two skill settings control the hourly chime.

## Time format

`use_24hour` is true when the session `time_format` is `full`.

| `time_format` | Clock | Example at 14:35 |
| :--- | :--- | :--- |
| `full` | 24-hour | fourteen thirty five |
| `half`, or any other value | 12-hour with a.m. or p.m. | two thirty five p.m. |

The same value selects the time on the GUI and on the Mark 1 faceplate (14:35 or 2:35 PM).

## Date format of the display

The session `date_format` selects the date that the GUI and the Mark 1 faceplate show. The spoken date does not use it.

| `date_format` | 4 March 2026 |
| :--- | :--- |
| `MDY` | 3/4/2026 |
| `DMY` | 04/3/2026 |
| `YMD` | 2026/3/04 |
| `YDM` | 2026/4/03 |

## The hourly chime

Set these keys in the `settings.json` file of the skill:

```json
{
    "play_hour_chime": true,
    "hour_sound": "clock-chime.mp3"
}
```

| Key | Type | Default | Effect |
| :--- | :--- | :--- | :--- |
| `play_hour_chime` | boolean | `false` | play a sound at the start of each hour |
| `hour_sound` | string | `casio-watch.wav` | the sound file: a full path, or a file name in `res/` |

The skill has two sounds in `res/`: `casio-watch.wav` and `clock-chime.mp3`. The skill schedules the next chime at the start of each hour, also when `play_hour_chime` is `false`.

---
[← Prev](speech.md) · [Home](index.md) · [Next →](timezone.md)
