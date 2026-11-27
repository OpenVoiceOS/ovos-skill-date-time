# ovos-skill-date-time documentation
<!-- agent-hint
covers: the reading order of the docs and one line for each page
source: docs/
generated: no
verify: diff <(ls docs/*.md | grep -v index.md | xargs -n1 basename | sort) <(grep -o '([a-z0-9-]*\.md)' docs/index.md | tr -d '()' | sort -u)
see: ../README.md
-->

The skill speaks the time, the date, the weekday and the number of days until a date, for your location or for a place that you name.

## Quickstart

```bash
uv pip install --prerelease=allow ovos-skill-date-time
```

Say "what time is it". The skill answers with a line from `time_current.dialog`, for example:

```text
It's <time>
```

The clock fills `<time>`. With the clock frozen at 14:35, a 12-hour session gives "two thirty five p.m." and a 24-hour session gives "fourteen thirty five".

## Pages

| Page | What you get there |
| :--- | :--- |
| [Phrases for each intent](usage.md) | the example phrases for each of the eleven intents |
| [How the skill speaks the time and the date](speech.md) | the writer for each slot, the chronologia reader, the writer for each locale |
| [Session values and settings](settings.md) | the 12- or 24-hour clock, the date format of the display, the hourly chime |
| [The timezone source](timezone.md) | the timezone for a request with and without a place |
| [Run the tests](testing.md) | the unit tests, the end-to-end tests with the frozen clock, the strict xfail rows |

## Libraries

| Library | Use in the skill |
| :--- | :--- |
| [ovos-workshop](https://github.com/OpenVoiceOS/ovos-workshop) | the skill framework |
| [chronologia](https://github.com/TigreGotico/chronologia) | reads the date or the length of time in a request |
| [ovos-date-parser](https://github.com/OpenVoiceOS/ovos-date-parser) | speaks the times and dates in the answers |
| [ovos-utterance-normalizer](https://github.com/OpenVoiceOS/ovos-utterance-normalizer) | normalizes the utterance of a request for a future time |
| [timezonefinder](https://github.com/jannikmi/timezonefinder) | gets the timezone at the coordinates of a place |
