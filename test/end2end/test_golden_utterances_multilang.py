"""Multilingual golden-utterance end-to-end coverage for ovos-skill-date-time.

Rows are checked with a real dispatched ``recognizer_loop:utterance`` and a
listener on the expected intent message type, following this repo's own
per-locale pattern (``test_intents_it_it.py``): one MiniCroft boot per
locale (``get_minicroft([SKILL_ID], max_wait=150, lang=LANG)``), never a
single shared boot with every locale as a secondary language -- that boot
path hits an open ovoscope harness bug that keeps ovos-skill-alerts' own
multilang suite skipped upstream.

``geocoder.osm`` is stubbed for every boot: several golden rows carry a
``{location}`` slot (e.g. "in Africa"), and intent routing does not depend
on the resolved coordinates, only on the utterance being recognized.
"""
import json
import time
from pathlib import Path
from unittest import mock

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import get_minicroft

SKILL_ID = "ovos-skill-date-time.openvoiceos"

PIPELINE = [
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-medium",
    "ovos-padacioso-pipeline-plugin-low",
]

END2END_DIR = Path(__file__).parent

LANGS = [
    "en-US", "an", "ca-ES", "cs-CZ", "da-DK", "de-DE", "es-ES", "eu-ES",
    "fa-IR", "fr-FR", "gl-ES", "hu-HU", "it-IT", "kab", "nl-NL", "pl-PL",
    "pt-BR", "pt-PT", "ru-RU", "fi-FI", "sv-FI", "sv-SE", "tr-TR",
]


def _load_rows(lang):
    path = END2END_DIR / f"golden_utterances_{lang}.jsonl"
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("needs_manual"):
                continue
            rows.append(row)
    return rows


ALL_ROWS = []
for _lang in LANGS:
    for _row in _load_rows(_lang):
        ALL_ROWS.append(_row)


def _golden_id(row):
    return f"{row['lang']}-{row['intent_label']}-{row['utterance']}"


GOLDEN_ROWS = [pytest.param(r, id=_golden_id(r)) for r in ALL_ROWS]

# Real locale-content defects found and fixed in-place during this pass
# (red-before/green-after verified), keyed by (lang, utterance):
KNOWN_BUGS = {}


@pytest.fixture(scope="module")
def geocoder_stub():
    class _FakeGeocodeResult:
        ok = True
        lat = 51.5074
        lng = -0.1278

    with mock.patch("geocoder.osm", return_value=_FakeGeocodeResult()):
        yield


@pytest.fixture(scope="module")
def minicroft_factory(geocoder_stub):
    cache = {"lang": None, "mc": None}

    def _get(lang):
        if cache["lang"] != lang:
            if cache["mc"] is not None:
                cache["mc"].stop()
            cache["mc"] = get_minicroft([SKILL_ID], max_wait=150, lang=lang)
            cache["lang"] = lang
        return cache["mc"]

    yield _get
    if cache["mc"] is not None:
        cache["mc"].stop()


def _dispatch_and_wait(mc, utterance, lang, intent_msg_type, deadline_s=45, settle_s=5):
    matched = []
    handler = lambda msg: matched.append(msg)
    mc.bus.on(intent_msg_type, handler)
    try:
        session = Session(f"golden-{lang}-{hash(utterance)}")
        session.lang = lang
        session.pipeline = PIPELINE
        message = Message(
            "recognizer_loop:utterance",
            {"utterances": [utterance], "lang": lang},
            {"session": session.serialize()},
        )
        deadline = time.monotonic() + deadline_s
        while not matched and time.monotonic() < deadline:
            mc.bus.emit(message)
            waited = time.monotonic() + settle_s
            while not matched and time.monotonic() < waited:
                time.sleep(0.2)
    finally:
        mc.bus.remove(intent_msg_type, handler)
    return matched


@pytest.mark.timeout(600)
@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=_golden_id)
def test_golden_utterance_multilang(minicroft_factory, row):
    mc = minicroft_factory(row["lang"])
    intent_msg_type = f"{SKILL_ID}:{row['intent_label']}"
    matched = _dispatch_and_wait(mc, row["utterance"], row["lang"], intent_msg_type)
    bug_key = (row["lang"], row["utterance"])
    if bug_key in KNOWN_BUGS and not matched:
        pytest.xfail(reason=f"known-bug: {KNOWN_BUGS[bug_key]}")
    assert matched, (
        f"[{row['lang']}] {row['utterance']!r} did not route to {intent_msg_type}"
    )
