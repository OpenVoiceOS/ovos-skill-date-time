"""Pin the spoken slot values that the ovos-date-parser nice_* writers give.

Each row sends one utterance through the m2v pipeline, with the clock frozen
at Wednesday 2026-03-04 14:35 Europe/Lisbon and a 12-hour session, and checks
the slot value in the ``speak`` message metadata. The expected values in
``spoken_pin_rows.py`` are written by hand from the locale grammar. A row
whose current output differs from the grammar is a strict xfail in
``KNOWN_DEFECTS``.

Weekday and month names compare without case: case is not spoken.
"""
import datetime
from unittest import mock

import pytest
import pytz
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_m2v_minicroft

from .spoken_pin_rows import ROWS

SKILL_ID = "ovos-skill-date-time.openvoiceos"
TZ = "Europe/Lisbon"
FROZEN = pytz.timezone(TZ).localize(datetime.datetime(2026, 3, 4, 14, 35))

# (lang, case) -> the defect, with the form a speaker says.
KNOWN_DEFECTS = {
    ("pt-PT", "date"): "the chronologia pt-PT writer joins the weekday and the date with no "
                       "comma: 'quarta-feira quatro de março de dois mil e vinte e seis'; the "
                       "weekday is an apposition before the date and takes a comma",
    ("da-DK", "date"): "da-DK year 2026 is written 'seks og tyve'; Danish writes "
                       "a compound numeral as one word: 'to tusind og seksogtyve'",
    ("da-DK", "year"): "da-DK year 2026 is written 'seks og tyve'; Danish writes "
                       "a compound numeral as one word: 'to tusind og seksogtyve'",
    ("it-IT", "date"): "it-IT year 2026 is written 'duemila ventisei'; Italian writes a cardinal "
                       "in letters as one word: 'duemilaventisei' (Accademia della Crusca, "
                       "consulenza 1077: 'la grafia prevista è, tranne rare eccezioni, "
                       "senza spazi: duecentodiecimila e non *duecento dieci mila')",
    ("it-IT", "year"): "it-IT year 2026 is written 'duemila ventisei'; Italian writes a cardinal "
                       "in letters as one word: 'duemilaventisei' (Accademia della Crusca, "
                       "consulenza 1077: 'la grafia prevista è, tranne rare eccezioni, "
                       "senza spazi: duecentodiecimila e non *duecento dieci mila')",
}


def _frozen_now(tz=None):
    return FROZEN.astimezone(tz or pytz.timezone(TZ))


@pytest.fixture(scope="module")
def minicroft_factory():
    cache = {}
    with mock.patch("ovos_skill_date_time.now_local", _frozen_now):
        def _get(lang):
            if lang not in cache:
                for mc in cache.values():
                    mc.stop()
                cache.clear()
                mc = get_m2v_minicroft([SKILL_ID], lang=lang)
                mc.intents.pipeline_plugins["ovos-m2v-pipeline"]._ensure_model(background_ok=False)
                cache[lang] = mc
            return cache[lang]

        yield _get
        for mc in cache.values():
            mc.stop()


def _spoken(mc, lang, utterance):
    session = Session(f"spoken-{lang}-{utterance}", time_format="half",
                      location={"lat": 38.7223, "lon": -9.1393, "tz": TZ})
    session.lang = lang
    message = Message("recognizer_loop:utterance",
                      {"utterances": [utterance], "lang": lang},
                      {"session": session.serialize(), "source": "A", "destination": "B"})
    capture = CaptureSession(mc)
    capture.capture(message, timeout=30)
    return [m for m in capture.finish() if m.msg_type in ("speak", "ovos.utterance.speak")]


PARAMS = []
for _lang, _rows in ROWS.items():
    for _row in _rows:
        marks = []
        if (_lang, _row[0]) in KNOWN_DEFECTS:
            marks.append(pytest.mark.xfail(strict=True, reason=KNOWN_DEFECTS[(_lang, _row[0])]))
        PARAMS.append(pytest.param(_lang, *_row, id=f"{_lang}-{_row[0]}", marks=marks))


@pytest.mark.timeout(600)
@pytest.mark.parametrize("lang,case,utterance,dialog,slot,expected", PARAMS)
def test_spoken_slot(minicroft_factory, lang, case, utterance, dialog, slot, expected):
    speaks = _spoken(minicroft_factory(lang), lang, utterance)
    metas = [(m.data.get("meta") or {}) for m in speaks]
    assert [meta.get("dialog") for meta in metas] == [dialog], (
        f"{utterance!r}: spoke {[m.data.get('utterance') for m in speaks]!r}")
    value = metas[0]["data"][slot]
    if case in ("weekday", "tomorrow", "weekday_of", "month"):
        value, expected = value.casefold(), expected.casefold()
    assert value == expected
    assert expected.casefold() in speaks[0].data["utterance"].casefold()
