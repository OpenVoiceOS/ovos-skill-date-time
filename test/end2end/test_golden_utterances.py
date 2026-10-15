"""Golden rows in every locale route to their intent on the m2v pipeline.

For each ``golden_utterances_<lang>.jsonl`` in this directory, one MiniCroft
loads the real skill in that language on the m2v prototype pipeline, the
model2vec engine built at boot from the skill's own ``.intent`` files. Each
row goes through that pipeline's high, medium and low tiers in order, and the
row passes when the first tier to match names its ``intent_label``. The test
prints the tier that matched each row and how many rows each tier took.

Each locale must pass at least ``MIN_MATCH_RATE`` of its rows, and every
intent with rows in a locale must match at least
``MIN_MATCHED_ROWS_PER_INTENT`` of them, except the measured gaps in
``GOLDEN_INTENT_GAPS``. All rows run,
including rows marked ``needs_manual`` or ``machine_generated``, and the test
prints every row that misses with the intent that matched instead.

Each ``negative_utterances_<lang>.jsonl`` holds requests for other skills.
On the same pipeline, a negative row that matches an intent of this skill
fails the locale, unless ``NEGATIVE_KNOWN_CLAIMS`` lists that claim.
"""
import json
from collections import Counter
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovoscope import M2V_PUBLISHED_MODEL, get_m2v_minicroft
from ovoscope.golden_minicroft import warm_m2v_models

SKILL_ID = "ovos-skill-date-time.openvoiceos"
M2V_PROTOTYPE = "ovos-m2v-prototype-pipeline"
STAGES = (("m2v-high", M2V_PROTOTYPE, "high"), ("m2v-medium", M2V_PROTOTYPE, "medium"),
          ("m2v-low", M2V_PROTOTYPE, "low"))
# m2v gives some rows a different answer on each boot, so the test gates on
# the share of rows that match per locale, not on each row. The rows are
# natural requests, not template copies; 0.6 is the floor set for them while
# some locales stay below 0.8.
MIN_MATCH_RATE = 0.6
# Every intent with rows in a locale must match at least this many of them, so
# a locale cannot pass the rate gate while one intent never routes at all.
MIN_MATCHED_ROWS_PER_INTENT = 1
# Intents that m2v gave no matched row in a locale, in two runs, with the
# measured routing of their rows. A listed gap is allowed, not required, so a
# row that matches on one boot does not fail the test. Every other intent
# keeps the floor above.
GOLDEN_INTENT_GAPS = {
    ("fa-IR", "what_time_is_it"): "2 of 3 rows go to what_day_is_it, 1 to what_time_will_it_be",
    ("fi-FI", "what_time_will_it_be"): "2 of 3 rows go to time_until, 1 to weekday_matches_date",
    ("it-IT", "what_time_will_it_be"): "2 of 3 rows match nothing, 1 goes to weekday_matches_date",
    ("pl-PL", "what_time_is_it"): "3 of 3 rows go to what_time_will_it_be",
    ("pt-PT", "what_time_will_it_be"): "3 of 3 rows match nothing",
    ("tr-TR", "what_time_will_it_be"): "1 of 3 rows goes to weekday_matches_date, 1 to time_until, "
                                       "1 to what_time_is_it",
}
END2END_DIR = Path(__file__).parent
# Locales whose requests for other skills the published m2v model cannot keep
# away from this skill, with the measured reason.
NEGATIVE_ENGINE_GAPS = {
    "pl-PL": "m2v claims 4 to 5 of 12 pl-PL requests for other skills, each run, "
             "at varying intents of this skill",
}
# Negative rows that m2v claimed for this skill in two separate runs. A listed
# claim is allowed, not required, so a row that flips between boots does not
# fail the test. Any other claim fails the locale.
NEGATIVE_KNOWN_CLAIMS = {
    "ca-ES": {"quin temps farà demà": "weekday_matches_date"},
    "es-ES": {"qué tiempo hará mañana": "weekday_for_date"},
    "fr-FR": {"combien font deux plus deux": "time_until"},
    "it-IT": {"che tempo farà domani": "weekday_for_date",
              "quanto fa due più due": "time_until"},
    "nl-NL": {"hoeveel is twee plus twee": "time_until"},
    "pt-BR": {"quanto é dois mais dois": "time_until"},
    "pt-PT": {"quanto é dois mais dois": "time_until"},
    "sv-FI": {"hur blir vädret i morgon": "weekday_matches_date",
              "vad är två plus två": "weekday_matches_date",
              "översätt god morgon till franska": "weekday_matches_date"},
    "sv-SE": {"hur blir vädret i morgon": "weekday_matches_date",
              "vad är två plus två": "weekday_matches_date",
              "översätt god morgon till franska": "weekday_matches_date"},
}


def _rows_by_lang(prefix="golden_utterances_"):
    rows = {}
    for path in sorted(END2END_DIR.glob(f"{prefix}*.jsonl")):
        lang = path.stem.removeprefix(prefix)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                row = json.loads(line)
                assert row["lang"] == lang, f"{path.name}:{number} has lang {row['lang']!r}"
                rows.setdefault(lang, []).append(row)
    return rows


ROWS = _rows_by_lang()
NEGATIVES = _rows_by_lang("negative_utterances_")


def _boot(lang):
    minicroft = get_m2v_minicroft([SKILL_ID], model=M2V_PUBLISHED_MODEL, lang=lang,
                                  classifier=False)
    warm_m2v_models(minicroft)
    return minicroft


def _match(minicroft, utterance, lang):
    """Return (stage, matched intent) from the first stage that claims the utterance."""
    message = Message("recognizer_loop:utterance",
                      {"utterances": [utterance], "lang": lang}, {"lang": lang})
    plugins = minicroft.intents.pipeline_plugins
    for stage, plugin, tier in STAGES:
        match = getattr(plugins[plugin], f"match_{tier}")([utterance], lang, message)
        if match:
            return stage, match.match_type
    return None, None


@pytest.mark.timeout(900)
@pytest.mark.parametrize("lang", sorted(ROWS))
def test_golden_rows_match_their_intent(lang):
    minicroft = _boot(lang)
    try:
        misses, lines = [], []
        stages = Counter()
        matched = {row["intent_label"]: 0 for row in ROWS[lang]}
        for row in ROWS[lang]:
            stage, got = _match(minicroft, row["utterance"], lang)
            stages[stage] += 1
            lines.append(f"{stage}: {row['utterance']!r} -> {got}")
            if got == f"{SKILL_ID}:{row['intent_label']}":
                matched[row["intent_label"]] += 1
            else:
                misses.append(f"{row['utterance']!r}: expected {row['intent_label']}, got {got}")
    finally:
        minicroft.stop()
    rate = 1 - len(misses) / len(ROWS[lang])
    print(f"[{lang}] {rate:.1%} of {len(ROWS[lang])} rows match; "
          f"stages {dict(stages)}",
          *lines, "misses:", *misses, sep="\n  ")
    assert rate >= MIN_MATCH_RATE, (
        f"[{lang}] {rate:.1%} of rows match, below {MIN_MATCH_RATE:.0%}:\n  " + "\n  ".join(misses)
    )
    starved = sorted(label for label, n in matched.items()
                     if n < MIN_MATCHED_ROWS_PER_INTENT and (lang, label) not in GOLDEN_INTENT_GAPS)
    assert not starved, (
        f"[{lang}] intents with fewer than {MIN_MATCHED_ROWS_PER_INTENT} matched rows: {starved}"
    )


@pytest.mark.timeout(900)
@pytest.mark.parametrize("lang", [
    pytest.param(lang, marks=pytest.mark.xfail(reason=NEGATIVE_ENGINE_GAPS[lang]))
    if lang in NEGATIVE_ENGINE_GAPS else lang
    for lang in sorted(NEGATIVES)
])
def test_negative_rows_match_no_intent_of_this_skill(lang):
    known = NEGATIVE_KNOWN_CLAIMS.get(lang, {})
    minicroft = _boot(lang)
    try:
        claims = []
        for row in NEGATIVES[lang]:
            stage, got = _match(minicroft, row["utterance"], lang)
            if got and got.startswith(f"{SKILL_ID}:"):
                claims.append((row["utterance"], got.removeprefix(f"{SKILL_ID}:")))
    finally:
        minicroft.stop()
    unknown = [f"{utterance!r}: matched {intent}" for utterance, intent in claims
               if known.get(utterance) != intent]
    print(f"[{lang}] {len(claims)} of {len(NEGATIVES[lang])} negative rows claimed, "
          f"{len(unknown)} not in NEGATIVE_KNOWN_CLAIMS", *unknown, sep="\n  ")
    assert not unknown, f"[{lang}] negative rows matched this skill:\n  " + "\n  ".join(unknown)


def test_every_shipping_locale_has_a_golden_file():
    golden = {p.stem.split("_", 2)[2] for p in END2END_DIR.glob("golden_utterances_*.jsonl")}
    locale_root = END2END_DIR.parents[1] / "locale"
    shipping = {d.name for d in locale_root.iterdir() if d.is_dir() and any(d.rglob("*.intent"))}
    assert golden == shipping, f"golden files {sorted(golden ^ shipping)} differ from shipping locales"


def test_every_en_us_intent_ships_in_every_locale():
    locale_root = END2END_DIR.parents[1] / "locale"
    reference = {p.name for p in (locale_root / "en-US").rglob("*.intent")}
    missing = {
        d.name: sorted(reference - {p.name for p in d.rglob("*.intent")})
        for d in sorted(locale_root.iterdir()) if d.is_dir() and any(d.rglob("*.intent"))
    }
    missing = {lang: names for lang, names in missing.items() if names}
    assert not missing, f"intent files of en-US missing from these locales: {missing}"
