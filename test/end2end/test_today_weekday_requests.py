"""A request about today's weekday is answered for today, through the full stack.

Each utterance goes through a MiniCroft, with the clock frozen to a Friday: on
the padatious and adapt pipeline, and on the m2v prototype pipeline. The utterance
normalizer and the intent engine run, so the handler gets the slots the engine
binds. The answer is the weekday of today, or a yes or no about today: never
the weekday of a later date.
"""
import datetime
import re
import time
from pathlib import Path
from unittest import TestCase, mock

import pytz
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import M2V_PUBLISHED_MODEL, get_m2v_minicroft, get_minicroft
from ovoscope.golden_minicroft import warm_m2v_models

SKILL_ID = "ovos-skill-date-time.openvoiceos"
LOCALE = Path(__file__).parent.parent.parent / "locale"
CLASSIC_PIPELINE = [
    "ovos-padatious-pipeline-plugin-high",
    "ovos-adapt-pipeline-plugin-high",
    "ovos-padatious-pipeline-plugin-medium",
    "ovos-adapt-pipeline-plugin-medium",
]
TZ = "Europe/Lisbon"
FRIDAY = pytz.UTC.localize(datetime.datetime(2024, 3, 15, 12, 0)).astimezone(pytz.timezone(TZ))
M2V_PIPELINE = [
    "ovos-m2v-prototype-pipeline-high",
    "ovos-m2v-prototype-pipeline-medium",
    "ovos-m2v-prototype-pipeline-low",
]
FRIDAY_INDEX = 4
LANGS = ("en-US", "fr-FR", "es-ES", "ca-ES", "gl-ES", "fa-IR", "kab", "pt-BR", "pt-PT",
         "cs-CZ", "nl-NL", "pl-PL", "sv-SE", "da-DK")

# (lang, utterance, weekday the request names, Monday is 0, or None)
REQUESTS = [
    ("en-US", "are we on Friday", 4),
    ("en-US", "are we on Monday", 0),
    ("en-US", "what day of the week is it", None),
    ("en-US", "hey can you tell me what day of the week it is", None),
    ("en-US", "do you know what day of the week it is", None),
    ("pt-PT", "Diz-me o dia da semana", None),
    ("da-DK", "hvad er det for en ugedag i dag", None),
    ("en-US", "what's the day of the week", None),
    ("en-US", "what’s the day of the week", None),
    ("fr-FR", "sommes-nous vendredi", 4),
    ("fr-FR", "sommes-nous lundi", 0),
    ("es-ES", "hoy estamos Viernes", 4),
    ("es-ES", "hoy estamos Lunes", 0),
    ("ca-ES", "som divendres", 4),
    ("ca-ES", "som dilluns", 0),
    ("gl-ES", "estamos a venres", 4),
    ("gl-ES", "estamos a luns", 0),
    ("fa-IR", "امروز جمعه هست", 4),
    ("fa-IR", "امروز دوشنبه هست", 0),
    ("fa-IR", "چند شنبه هست", None),
    ("fa-IR", "بهم بگو امروز چند شنبه هست", None),
    ("fa-IR", "امروز پنج\u200cشنبه هست", 3),
    ("fa-IR", "الآن توی سه\u200cشنبه هستیم", 1),
    ("fa-IR", "امروز یک\u200cشنبه هست", 6),
    ("kab", "Deg wass n lǧemɛa i nella?", 4),
    ("kab", "Deg wass n letnayen i nella?", 0),
]

# padatious and adapt route none of these; the m2v prototype does
M2V_ONLY_REQUESTS = [
    ("pt-PT", "em que dia da semana estamos", "weekday_current"),
    ("ca-ES", "quin dia de la setmana tenim", "weekday_current"),
    ("cs-CZ", "který den v týdnu je dneska", "weekday_current"),
    ("nl-NL", "welke weekdag hebben we", "weekday_current"),
    ("pl-PL", "jaki dziś dzień tygodnia", "weekday_current"),
    ("sv-SE", "vilken veckodag har vi", "weekday_current"),
    ("sv-SE", "vad är det för veckodag", "weekday_current"),
    ("es-ES", "en qué día estamos", "weekday_current"),
    ("fa-IR", "چند شنبه است", "weekday_current"),
]


def _templates(lang: str, dialog: str) -> list:
    """Regexes of the lines of a dialog file, each {slot} read as any text."""
    lines = (LOCALE / lang / "dialog" / f"{dialog}.dialog").read_text(encoding="utf-8").splitlines()
    return [re.compile(re.sub(r"\\\{\w+\\\}", ".+", re.escape(line.strip())), re.DOTALL)
            for line in lines if line.strip() and not line.startswith("#")]


def _is_line_of(spoken: str, lang: str, dialog: str) -> bool:
    return any(template.fullmatch(spoken) for template in _templates(lang, dialog))


class TodayWeekdayRequests:

    pipeline = None

    @classmethod
    def tearDownClass(cls):
        cls.minicroft.stop()

    def _ask(self, lang, utterance) -> str:
        spoken = []
        handler = lambda msg: spoken.append(msg.data.get("utterance", ""))
        self.minicroft.bus.on("speak", handler)
        try:
            session = Session(f"e2e-today-{lang}-{hash(utterance)}")
            session.lang = lang
            session.pipeline = self.pipeline
            session.location["tz"] = TZ
            message = Message("recognizer_loop:utterance",
                              {"utterances": [utterance], "lang": lang},
                              {"session": session.serialize(), "lang": lang})
            with mock.patch("ovos_skill_date_time.now_local", side_effect=lambda tz=None: FRIDAY):
                deadline = time.monotonic() + 45
                while not spoken and time.monotonic() < deadline:
                    self.minicroft.bus.emit(message)
                    waited = time.monotonic() + 5
                    while not spoken and time.monotonic() < waited:
                        time.sleep(0.2)
        finally:
            self.minicroft.bus.remove("speak", handler)
        self.assertTrue(spoken, f"{lang} {utterance!r} was not answered")
        return spoken[0]

    def test_each_request_is_answered_for_today(self):
        wrong = []
        for lang, utterance, weekday in REQUESTS:
            expected = ("weekday_current" if weekday is None else
                        "weekday_matches_date_today_yes" if weekday == FRIDAY_INDEX
                        else "weekday_matches_date_today_no")
            spoken = self._ask(lang, utterance)
            if not _is_line_of(spoken, lang, expected):
                wrong.append((lang, utterance, spoken, expected))
        self.assertEqual(wrong, [])

    def test_a_named_date_is_not_moved_a_week(self):
        # 2024-10-31 is a Thursday
        spoken = self._ask("en-US", "what day of the week is october 31")
        self.assertTrue(_is_line_of(spoken, "en-US", "weekday_at_date_future"), spoken)
        self.assertIn("thirty-first", spoken)
        self.assertIn("Thursday", spoken)


class TestClassicPipeline(TodayWeekdayRequests, TestCase):
    pipeline = CLASSIC_PIPELINE

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID], lang="en-US",
                                      secondary_langs=[lang for lang in LANGS if lang != "en-US"],
                                      default_pipeline=CLASSIC_PIPELINE, max_wait=600)


class TestM2vPipeline(TodayWeekdayRequests, TestCase):
    pipeline = M2V_PIPELINE

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_m2v_minicroft([SKILL_ID], model=M2V_PUBLISHED_MODEL, lang="en-US",
                                          secondary_langs=[lang for lang in LANGS if lang != "en-US"],
                                          classifier=False)
        warm_m2v_models(cls.minicroft)

    def test_a_request_that_only_m2v_routes_is_answered_for_today(self):
        wrong = []
        for lang, utterance, dialog in M2V_ONLY_REQUESTS:
            spoken = self._ask(lang, utterance)
            if not _is_line_of(spoken, lang, dialog):
                wrong.append((lang, utterance, spoken))
        self.assertEqual(wrong, [])

    # the m2v engine binds no slot, so the parser alone reads the date
    def test_a_date_that_cannot_be_read_is_an_error(self):
        for utterance in ("which day of the week will 12/25/2024 land on",
                          "what day of the week does 12/25/2024 land on"):
            spoken = self._ask("en-US", utterance)
            self.assertTrue(_is_line_of(spoken, "en-US", "extract_date_error"), (utterance, spoken))
