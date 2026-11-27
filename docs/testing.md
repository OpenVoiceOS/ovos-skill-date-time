# Run the tests
<!-- agent-hint
covers: unit tests, end-to-end tests with the frozen clock, the strict xfail rows, golden utterances, the docs checks
source: test/, .github/workflows/coverage.yml, .github/workflows/ovoscope.yml
generated: no
verify: (p=$(grep -o '^| `[a-z]*-[A-Z]*` | `[a-z]*`' docs/testing.md | tr -d '`| ' | sort | tr '\n' ' '); c=$(grep -o '("[a-z]*-[A-Z]*", "[a-z]*")' test/end2end/test_spoken_writers.py | tr -d '()" ' | tr ',' ' ' | sed 's/ //' | sort | tr '\n' ' '); [ "$p" = "$c" ] || { echo "xfails: page [$p], code [$c]"; exit 1; }; python docs/verify_phrases.py >/dev/null || exit 1; echo OK)
see: speech.md
-->

Run the unit tests and the end-to-end tests from the repository root:

```bash
uv venv && uv pip install --python .venv/bin/python --prerelease=allow -e '.[test]'
.venv/bin/python -m pytest test/unittests
.venv/bin/python -m pytest test/end2end
```

CI runs `test/unittests` in `coverage.yml` and `test/end2end/` in `ovoscope.yml`.

## End-to-end tests with a frozen clock

A spoken time or date changes with the clock. `test/end2end/test_spoken_writers.py` removes the clock:

1. It patches `ovos_skill_date_time.now_local` to return Wednesday 4 March 2026, 14:35, Europe/Lisbon.
2. It sends each utterance in a session with `time_format="half"` and a Lisbon location.
3. It sends the utterance through the m2v intent pipeline of ovoscope and reads the `speak` messages.
4. It compares the slot value in the message metadata with the value in `test/end2end/spoken_pin_rows.py`.

The expected values in `spoken_pin_rows.py` come from the grammar of each locale, not from ovos-date-parser. Weekday and month names compare without letter case. Run one locale:

```bash
.venv/bin/python -m pytest test/end2end/test_spoken_writers.py -k en-US -q
```

## Strict xfail rows

A row where ovos-date-parser writes a form that the grammar does not allow is a strict xfail in `KNOWN_DEFECTS`. A strict xfail fails the suite when the row starts to pass, so the fix in ovos-date-parser shows at once.

| Locale | Case | ovos-date-parser writes | The grammar asks for |
| :--- | :--- | :--- | :--- |
| `da-DK` | `date` | seks og tyve | to tusind og seksogtyve |
| `da-DK` | `year` | seks og tyve | to tusind og seksogtyve |
| `it-IT` | `date` | duemila ventisei | duemilaventisei |
| `it-IT` | `year` | duemila ventisei | duemilaventisei |

Danish and Italian write a compound numeral as one word. The it-IT reason cites Accademia della Crusca, consulenza 1077.

## Other end-to-end tests

- `test_intents_en_us.py` and `test_intents_it_it.py` check only the routing.
- `test_effect_year_day_and_chime.py` checks the spoken year and day against `now_local`, and the hourly chime with the event scheduler on.
- `golden_utterances_<lang>.jsonl` holds the utterances that must start each intent, and `negative_utterances_<lang>.jsonl` holds the utterances that must not start this skill. `test_golden_utterances.py` reads both.

## Docs checks

`docs/verify_phrases.py` sends each phrase in `usage.md` through a padacioso container of the en-US `.intent` files. It exits 1 when a phrase does not start the intent of its section:

```bash
python docs/verify_phrases.py
```

Each page has a `verify` line in its agent hint. The line compares the values on the page with the code.

---
[← Prev](timezone.md) · [Home](index.md)
