# <img src='https://raw.githack.com/FortAwesome/Font-Awesome/master/svgs/solid/calendar.svg' card_color='#22a7f0' width='50' height='50' style='vertical-align:bottom'/> Date and Time
<!-- agent-hint
covers: what the skill does, install, a quickstart and the docs link table
source: pyproject.toml
generated: no
verify: diff <(ls docs/*.md | xargs -n1 basename | sort) <(grep -o '(docs/[a-z0-9-]*\.md)' README.md | sed 's%(docs/%%; s%)%%' | sort -u)
see: docs/index.md
-->

An OVOS skill that speaks the time, the date, the weekday, the month, the year and the number of days until a date. It answers for your location or for a place that you name. It works with no network, except for the lookup of a named place.

## Install

```bash
uv pip install --prerelease=allow ovos-skill-date-time
```

OVOS loads the skill through the `opm.skill` entry point `ovos-skill-date-time.openvoiceos`.

## Quickstart

```text
"what time is it"                     -> It's <time>
"how many days until march twentieth" -> It's <date>, <num_days> from now
```

The skill selects one line of the dialog file for each answer. The clock fills the slots. With the clock frozen at 14:35 on 4 March 2026, `<time>` is "two thirty five p.m." in a 12-hour session, and `<num_days>` is "sixteen days".

## Documentation

| Page | Contents |
| :--- | :--- |
| [Docs index](docs/index.md) | the reading order |
| [Phrases for each intent](docs/usage.md) | example phrases and the intent that each one starts |
| [How the skill speaks the time and the date](docs/speech.md) | the writer for each slot and for each locale |
| [Session values and settings](docs/settings.md) | the 12- or 24-hour clock, the display date, the hourly chime |
| [The timezone source](docs/timezone.md) | the timezone for a request with and without a place |
| [Run the tests](docs/testing.md) | unit tests, end-to-end tests with the frozen clock, strict xfail rows |

## License and credits

[Apache-2.0](./LICENSE). Original skill by Mycroft AI. Sounds: [casio-watch.wav by Pablobd](https://freesound.org/people/Pablobd/sounds/492481/) (CC0 1.0), [clock-chime.mp3 by ecfike](https://pixabay.com/sound-effects/clock-chime-88027/) (Pixabay Content License). Timezone boundaries from [timezonefinder-data](https://github.com/jannikmi/timezonefinder), built from [timezone-boundary-builder](https://github.com/evansiroky/timezone-boundary-builder) on [OpenStreetMap](https://www.openstreetmap.org/copyright) data, under the [Open Database License (ODbL) v1.0](https://opendatacommons.org/licenses/odbl/1-0/). The `timezonefinder` package installs that database unmodified. A changed copy of the boundary data that you pass on must be under the ODbL. The `NOTICE` file holds the full attribution.
