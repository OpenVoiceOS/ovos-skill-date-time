"""weekday_for_date answers for a date, for today, and for yes/no questions.

Each utterance is matched by padacioso against the locale's own
``weekday_for_date.intent`` and its slots go to the handler as the engine
binds them, or as none, because m2v binds no slots. "Now" is pinned to a
Saturday so the answers are fixed.
"""
import os
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest import mock

import pytz
from ovos_bus_client.message import Message
from ovos_date_parser import extract_datetime, nice_date, nice_weekday
from padacioso import IntentContainer

SKILL_ID = "ovos-skill-date-time.openvoiceos"
LOCALE_DIR = Path(__file__).parent.parent.parent / "locale"
NOW = pytz.timezone("Europe/Copenhagen").localize(datetime(2026, 10, 17, 12, 0))

# (lang, utterance, weekday the request names, Monday is 0; None when it names none
# or asks which of several it is). Each phrasing was a what_weekday_is_it line
# that spoke today's weekday before the intents merged.
TODAY_REQUESTS = [
    ("an", "hue somos a luns?", 0),
    ("an", "hue somos a martes?", 1),
    ("an", "hue somos a sabado?", 5),
    ("an", "hue somos a viernes?", 4),
    ("ca-ES", "som dilluns", 0),
    ("ca-ES", "som dimarts", 1),
    ("ca-ES", "som dimecres", 2),
    ("ca-ES", "som dissabte", 5),
    ("ca-ES", "som diumenge", 6),
    ("ca-ES", "som divendres", 4),
    ("cs-CZ", "pověz mi, jestli je dnes pondělí nebo úterý", None),
    ("en-US", "are we on Friday", 4),
    ("en-US", "are we on Monday", 0),
    ("en-US", "are we on Saturday", 5),
    ("en-US", "are we on Sunday", 6),
    ("en-US", "are we on Tuesday", 1),
    ("en-US", "are we on Wednesday", 2),
    ("en-US", "can you tell me the day of the week", None),
    ("en-US", "do you know the day of the week", None),
    ("en-US", "tell me the day of the week", None),
    ("en-US", "what day of the week is it", None),
    ("en-US", "what’s the day of the week", None),
    ("en-US", "what’s today's day of the week", None),
    ("en-US", "which day of the week is it", None),
    ("es-CO", "hoy estamos Domingo", 6),
    ("es-CO", "hoy estamos Lunes", 0),
    ("es-CO", "hoy estamos Martes", 1),
    ("es-CO", "hoy estamos Viernes", 4),
    ("es-ES", "hoy estamos Domingo", 6),
    ("es-ES", "hoy estamos Lunes", 0),
    ("es-ES", "hoy estamos Martes", 1),
    ("es-ES", "hoy estamos Viernes", 4),
    ("fa-IR", "امروز جمعه هست", 4),
    ("fa-IR", "امروز شنبه هست", 5),
    ("fa-IR", "امروز یک‌شنبه هست", 6),
    ("fa-IR", "امروز دوشنبه هست", 0),
    ("fa-IR", "امروز سه‌شنبه هست", 1),
    ("fa-IR", "امروز چهارشنبه هست", 2),
    ("fa-IR", "الآن توی جمعه هستیم", 4),
    ("fa-IR", "الآن توی شنبه هستیم", 5),
    ("fa-IR", "الآن توی یک‌شنبه هستیم", 6),
    ("fa-IR", "الآن توی دوشنبه هستیم", 0),
    ("fa-IR", "الآن توی سه‌شنبه هستیم", 1),
    ("fa-IR", "الآن توی چهارشنبه هستیم", 2),
    ("fa-IR", "الآن چند شنبه هست", None),
    ("fa-IR", "بهم بگو الآن چند شنبه هست", None),
    ("fa-IR", "بهم بگو امروز چند شنبه هست", None),
    ("fa-IR", "چند شنبه هستیم", None),
    ("fa-IR", "چند شنبه هست", None),
    ("fr-FR", "sommes-nous dimanche", 6),
    ("fr-FR", "sommes-nous lundi", 0),
    ("fr-FR", "sommes-nous mardi", 1),
    ("fr-FR", "sommes-nous mercredi", 2),
    ("fr-FR", "sommes-nous samedi", 5),
    ("fr-FR", "sommes-nous vendredi", 4),
    ("gl-ES", "estamos a domingo", 6),
    ("gl-ES", "estamos a luns", 0),
    ("gl-ES", "estamos a martes", 1),
    ("gl-ES", "estamos a mércores", 2),
    ("gl-ES", "estamos a sábado", 5),
    ("gl-ES", "estamos a venres", 4),
    ("it-IT", "oggi è lunedì o martedì o che giorno", None),
    ("kab", "Deg wass n lǧemɛa i nella?", 4),
    ("kab", "Deg wass n letnayen i nella?", 0),
    ("kab", "Deg wass n ssebt i nella?", 5),
    ("kab", "Deg wass n lḥedd i nella?", 6),
    ("kab", "Deg wass n lexmis i nella?", 3),
    ("kab", "Deg wass n ttlata i nella?", 1),
    ("kab", "Deg wass n larebɛa i nella?", 2),
    ("kab", "D larebɛa?", 2),
    ("kab", "Ass-a d larebɛa?", 2),
]


THURSDAY = 3

# (lang, utterance, date the utterance names, index of the weekday it names or None).
# Dates are the next occurrence after the pinned Saturday, 2026-10-17.
OTHER_DAY_QUESTIONS = [
    ("en-US", "is valentine's day on a thursday", date(2027, 2, 14), THURSDAY),
    ("en-US", "does new year's eve fall on a thursday", date(2026, 12, 31), THURSDAY),
    ("en-US", "is christmas on a saturday", date(2026, 12, 25), 5),
    ("es-ES", "san valentín cae en jueves este año", date(2027, 2, 14), THURSDAY),
    ("es-CO", "san valentín cae en jueves este año", date(2027, 2, 14), THURSDAY),
    ("gl-ES", "o Día da Nai cae en xoves?", date(2027, 5, 2), THURSDAY),
    ("it-IT", "Capodanno cadrà di giovedì?", date(2027, 1, 1), THURSDAY),
    ("pt-BR", "o dia de Ano Novo vai cair numa quinta-feira", date(2027, 1, 1), THURSDAY),
    ("pt-PT", "o Dia de Ano Novo vai calhar a uma quinta-feira", date(2027, 1, 1), THURSDAY),
    ("ru-RU", "Новый год выпадет на четверг?", date(2027, 1, 1), THURSDAY),
    ("sv-SE", "blir nyårsafton en torsdag", date(2026, 12, 31), THURSDAY),
    ("sv-FI", "blir nyårsafton en torsdag", date(2026, 12, 31), THURSDAY),
    ("pt-BR", "1º de janeiro cai numa quinta-feira", date(2027, 1, 1), THURSDAY),
    ("pt-BR", "31 de outubro vai ser quinta-feira", date(2026, 10, 31), THURSDAY),
    ("pt-PT", "31 de outubro calha a uma quinta-feira", date(2026, 10, 31), THURSDAY),
    # the Finnish name for the weekday is in the essive case, so no weekday is named
    ("fi-FI", "onko uudenvuodenaatto torstaina", date(2026, 12, 31), None),
    # Father's Day is 19 March in Spain and Labour Day 1 May. The Basque name
    # for the weekday is in the inessive case, so no weekday is named.
    ("eu-ES", "asteko zein egunetan da Aitaren eguna", date(2027, 3, 19), None),
    ("eu-ES", "Aitaren eguna ostegunean al da", date(2027, 3, 19), None),
    ("eu-ES", "asteko zein egunetan da Langilearen eguna", date(2027, 5, 1), None),
    # the bare "new year" is Nowruz, 1 Farvardin 1406: the March equinox falls
    # at 20:25 UTC on 20 March 2027, 23:55 in Tehran, so the year starts on the 21st
    ("fa-IR", "سال نو پنجشنبه میفته؟", date(2027, 3, 21), THURSDAY),
    ("fa-IR", "سال نو چه روزی از هفته میفته", date(2027, 3, 21), None),
]

# questions that name no other day and are about today
PLAIN_WEEKDAY_QUESTIONS = [
    ("pt-BR", "Diga-me o dia da semana"), ("pt-BR", "hoje é que dia da semana"),
    ("pt-PT", "Diz-me o dia da semana"), ("pt-PT", "em que dia da semana estamos"),
    ("pt-PT", "que dia da semana é hoje por favor"),
    ("ca-ES", "quin dia de la setmana tenim"),
    ("cs-CZ", "který den v týdnu je dneska"),
    ("nl-NL", "welke weekdag hebben we"), ("pl-PL", "jaki dziś dzień tygodnia"),
    ("sv-FI", "vilken veckodag har vi"), ("sv-FI", "vad är det för veckodag"),
    ("sv-SE", "vilken veckodag har vi idag"), ("sv-SE", "vad är det för veckodag"),
    ("es-ES", "en qué día estamos"), ("es-CO", "en qué día estamos"),
    ("pl-PL", "jaki to dzień tygodnia"), ("fa-IR", "چند شنبه است"),
    ("en-US", "do you know what day of the week it is"),
    ("en-US", "hey can you tell me what day of the week it is"),
    ("da-DK", "hvad er det for en ugedag i dag"),
    ("en-US", "what day of the week is my birthday"),
]


class TestWeekdayForDate(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._xdg = tempfile.TemporaryDirectory(prefix="date-time-weekday-")
        cls._saved = {}
        for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME",
                    "XDG_STATE_HOME", "XDG_CACHE_HOME"):
            cls._saved[var] = os.environ.get(var)
            os.environ[var] = os.path.join(cls._xdg.name, var.lower())

        from ovos_skill_date_time import TimeSkill
        from ovos_utils.messagebus import FakeBus

        cls.skill = TimeSkill()
        cls.skill._startup(FakeBus(), SKILL_ID)

    @classmethod
    def tearDownClass(cls):
        cls.skill.shutdown()
        for var, value in cls._saved.items():
            if value is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = value
        cls._xdg.cleanup()

    def _speak(self, data, lang, now=NOW):
        message = Message("weekday_for_date", data)
        with mock.patch.object(self.skill, "get_datetime", return_value=now), \
                mock.patch.object(type(self.skill), "lang",
                                  new_callable=mock.PropertyMock,
                                  return_value=lang), \
                mock.patch.object(self.skill, "speak_dialog") as speak:
            self.skill.handle_weekday(message)
        speak.assert_called_once()
        args = speak.call_args.args
        return args[0], (args[1] if len(args) > 1 else {})

    def _padacioso(self, utterance, lang="en-US"):
        """Answer for the slots padacioso binds from the locale's templates."""
        locale = LOCALE_DIR / lang
        samples = [line.strip() for line in
                   (locale / "intents" / "weekday_for_date.intent")
                   .read_text(encoding="utf-8").splitlines()
                   if line.strip() and not line.startswith("#")]
        container = IntentContainer()
        container.add_intent("weekday_for_date", samples)
        for entity in ("date", "weekday"):
            container.add_entity(entity, [
                line.strip() for line in
                (locale / f"{entity}.entity").read_text(encoding="utf-8").splitlines()
                if line.strip()])
        match = container.calc_intent(utterance)
        self.assertEqual(match["name"], "weekday_for_date", utterance)
        return self._speak({**match["entities"], "utterance": utterance}, lang)

    def _slotless(self, utterance, lang="en-US", now=NOW):
        """Answer when the engine binds no slot at all."""
        return self._speak({"utterance": utterance}, lang, now)

    def test_a_request_without_a_date_is_about_today(self):
        # 2026-10-17 is a Saturday
        for answer in (self._padacioso("what weekday is it"),
                       self._slotless("what weekday is it")):
            self.assertEqual(answer[0], "weekday_current")
            self.assertEqual(answer[1]["weekday"], "Saturday")

    def test_a_word_of_a_dateless_request_bound_as_the_date_is_not_a_date(self):
        # the pipeline binds "it" to the date slot of "what weekday is it"
        for lang, utterance, slot in (
                ("en-US", "what weekday is it", "it"),
                ("de-DE", "welcher wochentag ist es", "es")):
            key, _ = self._speak({"utterance": utterance, "date": slot}, lang)
            self.assertEqual(key, "weekday_current", utterance)

    def test_a_polite_tail_bound_as_the_date_is_not_a_date(self):
        key, _ = self._speak({"utterance": "what weekday is it please",
                              "date": "it please"}, "en-US")
        self.assertEqual(key, "weekday_current")

    def test_words_the_request_lines_lack_are_not_a_dateless_slot(self):
        for utterance, slot in (("what weekday is it in tokyo", "it in tokyo"),
                                ("what day of the week is blorp", "blorp")):
            key, _ = self._speak({"utterance": utterance, "date": slot}, "en-US")
            self.assertEqual(key, "extract_date_error", utterance)

    def test_the_weekday_named_twice_blanks_only_the_target(self):
        # 2026-10-17 is a Saturday; next Friday is the 23rd
        for utterance, expected in (
                ("is next friday a friday", "weekday_matches_date_future_yes"),
                ("is next friday a monday", "weekday_matches_date_future_no")):
            for data in ({"utterance": utterance},
                         {"utterance": utterance, "date": "next friday a"}):
                key, _ = self._speak(data, "en-US")
                self.assertEqual(key, expected, (utterance, data))

    def test_a_hyphenated_weekday_split_by_the_engine(self):
        # 2026-10-19 is a Monday, 2026-10-15 a Thursday
        for lang in ("pt-PT", "pt-BR"):
            for utterance, expected in (
                    ("é depois de amanhã segunda-feira",
                     "weekday_matches_date_future_yes"),
                    ("é depois de amanhã segunda - feira",
                     "weekday_matches_date_future_yes"),
                    ("foi anteontem quinta-feira", "weekday_matches_date_past_yes"),
                    ("foi anteontem quinta - feira", "weekday_matches_date_past_yes"),
                    ("foi anteontem sexta - feira", "weekday_matches_date_past_no")):
                key, _ = self._slotless(utterance, lang)
                self.assertEqual(key, expected, (lang, utterance))

    def test_a_slotless_request_names_its_date(self):
        key, data = self._slotless("welcher wochentag ist morgen", "de-DE")
        self.assertEqual(key, "weekday_at_date_future")
        self.assertEqual(data["weekday"], "Sonntag")

    def test_a_named_date_gets_its_weekday(self):
        key, data = self._padacioso("what weekday is christmas")
        expected = extract_datetime("christmas", anchorDate=NOW, lang="en-US")
        self.assertIsNotNone(expected)
        self.assertEqual(key, "weekday_at_date_future")
        self.assertEqual(data["weekday"], "Friday")

    def test_today_is_not_the_weekday_named_in_a_yes_no_question(self):
        for answer in (self._padacioso("is today a monday"),
                       self._slotless("is today a monday")):
            self.assertEqual(answer[0], "weekday_matches_date_today_no")
            self.assertEqual(answer[1]["actual_weekday"], "Saturday")

    def test_a_slot_that_captured_the_weekday_is_not_the_date(self):
        # m2v binds the span "today a monday" to the date slot
        for utterance, slot, expected in (
                ("is today a monday", "today a monday",
                 "weekday_matches_date_today_no"),
                ("is tomorrow a sunday", "tomorrow a sunday",
                 "weekday_matches_date_future_yes"),
                ("was yesterday a friday", "yesterday a friday",
                 "weekday_matches_date_past_yes")):
            key, _ = self._speak({"utterance": utterance, "date": slot}, "en-US")
            self.assertEqual(key, expected, utterance)

    def test_today_is_the_weekday_named_in_a_yes_no_question(self):
        key, _ = self._slotless("is today a saturday")
        self.assertEqual(key, "weekday_matches_date_today_yes")

    def test_a_yes_no_question_about_a_date(self):
        key, _ = self._slotless("is christmas on a friday")
        self.assertEqual(key, "weekday_matches_date_future_yes")

    def test_a_what_question_about_a_named_weekday_is_not_yes_no(self):
        # 2026-10-17 is a Saturday; next Friday is the 23rd
        for lang, utterance, weekday in (
                ("en-US", "tell me what weekday next friday is", "Friday"),
                ("en-US", "do you know what day of the week next friday is",
                 "Friday"),
                ("en-US", "what is the day of the week of next friday", "Friday"),
                ("de-DE", "kannst du mir sagen welcher wochentag nächster freitag ist",
                 "Freitag"),
                ("de-DE", "sag mir welcher wochentag nächster freitag ist",
                 "Freitag"),
                ("fr-FR", "le prochain vendredi c'est quel jour", "vendredi")):
            key, data = self._slotless(utterance, lang)
            self.assertEqual(key, "weekday_at_date_future", utterance)
            self.assertEqual(data["weekday"].lower(), weekday.lower(), utterance)

    def test_a_what_question_is_not_yes_no_when_padacioso_binds_the_date(self):
        key, data = self._padacioso("tell me what weekday next friday is")
        self.assertEqual(key, "weekday_at_date_future")
        self.assertEqual(data["weekday"], "Friday")

    def test_yes_no_questions_in_other_languages(self):
        for lang, utterance, expected in (
                ("en-US", "is it friday", "weekday_matches_date_today_no"),
                ("en-US", "will tomorrow be a sunday",
                 "weekday_matches_date_future_yes"),
                ("de-DE", "ist heute samstag", "weekday_matches_date_today_yes"),
                ("es-ES", "es mañana domingo", "weekday_matches_date_future_yes"),
                ("pt-PT", "é amanhã domingo", "weekday_matches_date_future_yes")):
            key, _ = self._slotless(utterance, lang)
            self.assertEqual(key, expected, utterance)

    def test_a_closing_yes_no_marker_is_read(self):
        with mock.patch.object(type(self.skill), "lang",
                               new_callable=mock.PropertyMock,
                               return_value="tr-TR"):
            self.assertTrue(self.skill._is_yes_no_question("bugün pazartesi mi"))
            self.assertFalse(self.skill._is_yes_no_question("hangi gün pazartesi"))

    def test_a_relative_date_is_read_whole(self):
        # m2v cuts the slot at "after today a sunday" and "from today a saturday"
        for utterance, slot, expected in (
                ("is the day after today a sunday", "after today a sunday",
                 "weekday_matches_date_future_yes"),
                ("is the day after today a monday", "after today a monday",
                 "weekday_matches_date_future_no"),
                ("is a week from today a saturday", "from today a saturday",
                 "weekday_matches_date_future_yes"),
                ("is a week from today a sunday", "from today a sunday",
                 "weekday_matches_date_future_no")):
            for data in ({"utterance": utterance, "date": slot},
                         {"utterance": utterance}):
                key, _ = self._speak(data, "en-US")
                self.assertEqual(key, expected, (utterance, data))

    def test_text_that_is_not_a_date_is_an_error(self):
        key, _ = self._padacioso("what day of the week is blorp")
        self.assertEqual(key, "extract_date_error")

    def test_a_weekday_in_a_what_question_is_not_a_yes_no_question(self):
        key, data = self._slotless("what day of the week is next monday")
        self.assertEqual(key, "weekday_at_date_future")
        self.assertEqual(data["weekday"], "Monday")

    def test_the_table_holds_the_71_phrasings_of_11_locales(self):
        self.assertEqual(len(TODAY_REQUESTS), 71)
        self.assertEqual(len({lang for lang, _, _ in TODAY_REQUESTS}), 11)

    def test_each_phrasing_is_answered_for_today(self):
        saturday = NOW.weekday()
        self.assertEqual(saturday, 5)
        wrong = []
        for lang, utterance, weekday in TODAY_REQUESTS:
            expected = ("weekday_current" if weekday is None else
                        "weekday_matches_date_today_yes" if weekday == saturday
                        else "weekday_matches_date_today_no")
            key, _ = self._slotless(utterance, lang)
            if key != expected:
                wrong.append((lang, utterance, key, expected))
        self.assertEqual(wrong, [], f"{len(wrong)} of {len(TODAY_REQUESTS)} phrasings")

    def test_a_choice_between_weekdays_is_answered_for_the_date_it_names(self):
        for utterance, expected in (("is it friday or saturday", "weekday_current"),
                                    ("is tomorrow monday or sunday", "weekday_at_date_future")):
            key, _ = self._slotless(utterance, "en-US")
            self.assertEqual(key, expected, utterance)

    def test_an_article_before_a_word_of_the_request_is_not_a_number(self):
        # 2026-10-24 is the Saturday of the next week; "a week from today" names it
        key, data = self._slotless("what day is a week from today", "en-US")
        self.assertEqual(key, "weekday_at_date_future")
        self.assertEqual(data["weekday"], "Saturday")


    def test_a_persian_name_split_by_a_joiner_or_a_space_is_one_name(self):
        # the utterance normalizer turns the joiner into a space; 2026-10-17 is a Saturday
        for utterance, expected in (
                ("امروز شنبه هست", "weekday_matches_date_today_yes"),
                ("امروز یک\u200cشنبه هست", "weekday_matches_date_today_no"),
                ("امروز یک شنبه هست", "weekday_matches_date_today_no"),
                ("امروز یکشنبه هست", "weekday_matches_date_today_no"),
                ("امروز پنج شنبه هست", "weekday_matches_date_today_no"),
                ("الآن توی سه شنبه هستیم", "weekday_matches_date_today_no")):
            key, data = self._slotless(utterance, "fa-IR")
            self.assertEqual(key, expected, utterance)

    def test_the_ascii_apostrophe_does_not_make_the_week_a_number(self):
        for utterance in ("what's the day of the week", "what’s the day of the week",
                          "what's today's day of the week"):
            key, _ = self._slotless(utterance, "en-US")
            self.assertEqual(key, "weekday_current", utterance)

    def test_a_date_slot_inside_a_weekday_question_is_no_date(self):
        # m2v binds the Persian "which weekday" idiom's weekday name as the date
        for utterance in ("چند شنبه هست", "بهم بگو امروز چند شنبه هست"):
            key, _ = self._speak({"utterance": utterance, "date": "شنبه"}, "fa-IR")
            self.assertEqual(key, "weekday_current", utterance)

    def test_a_date_that_cannot_be_read_is_an_error_not_today(self):
        for utterance in ("which day of the week will 12/25/2024 land on",
                          "what day of the week does 12/25/2024 land on"):
            key, _ = self._slotless(utterance, "en-US")
            self.assertEqual(key, "extract_date_error", utterance)

    def test_a_named_date_is_not_moved_a_week_when_no_slot_is_bound(self):
        # 2026-10-28 is a Wednesday; a week later is November 4
        key, data = self._slotless("what day of the week is october 28", "en-US")
        self.assertEqual(key, "weekday_at_date_future")
        self.assertEqual(data["weekday"], "Wednesday")
        self.assertIn("twenty-eighth", data["date"])
        self.assertNotIn("november", data["date"])

    def test_an_article_that_opens_a_date_stays_a_number(self):
        for utterance in ("is the day after today a sunday",):
            key, _ = self._slotless(utterance, "en-US")
            self.assertEqual(key, "weekday_matches_date_future_yes")


    def test_a_plain_weekday_question_with_words_the_lines_lack_is_about_today(self):
        # each question was answered with today's weekday before the intents merged
        for lang, utterance in (
                ("pt-BR", "Diga-me o dia da semana"), ("pt-PT", "Diz-me o dia da semana"),
                ("pt-PT", "em que dia da semana estamos"), ("ca-ES", "quin dia de la setmana tenim"),
                ("cs-CZ", "který den v týdnu je dneska"), ("nl-NL", "welke weekdag hebben we"),
                ("pl-PL", "jaki dziś dzień tygodnia"), ("sv-SE", "vilken veckodag har vi"),
                ("sv-FI", "vad är det för veckodag"), ("es-ES", "en qué día estamos"),
                ("fa-IR", "چند شنبه است")):
            key, _ = self._slotless(utterance, lang)
            self.assertEqual(key, "weekday_current", (lang, utterance))

    def test_the_day_of_the_week_inside_a_request_is_not_a_week_offset(self):
        for utterance in ("tell me what day of the week it is",
                          "do you know what day of the week it is",
                          "hey can you tell me what day of the week it is"):
            key, _ = self._slotless(utterance, "en-US")
            self.assertEqual(key, "weekday_current", utterance)

    def test_a_bare_article_bound_as_the_date_is_no_date(self):
        # m2v binds the Danish "en" ("a"), which the parser reads as the number 1
        key, _ = self._speak({"utterance": "hvad er det for en ugedag", "date": "en"}, "da-DK")
        self.assertEqual(key, "weekday_current")


    def test_a_yes_no_question_that_opens_with_today_or_haben_wir(self):
        # 2026-10-17 is a Saturday
        for lang, utterance, expected in (
                ("de-DE", "haben wir heute Dienstag", "weekday_matches_date_today_no"),
                ("de-DE", "haben wir heute Samstag", "weekday_matches_date_today_yes"),
                ("en-US", "today's sunday, isn't it", "weekday_matches_date_today_no"),
                ("en-US", "today's saturday, isn't it", "weekday_matches_date_today_yes")):
            key, _ = self._slotless(utterance, lang)
            self.assertEqual(key, expected, (lang, utterance))

    def test_a_named_holiday_or_date_is_not_today(self):
        for lang, utterance, day, named in OTHER_DAY_QUESTIONS:
            noon = datetime.combine(day, time(12))
            actual = nice_weekday(noon, lang=lang)
            key, data = self._slotless(utterance, lang)
            if named is None:
                self.assertEqual((key, data["weekday"]), ("weekday_at_date_future", actual),
                                 (lang, utterance))
                self.assertEqual(data["date"], nice_date(noon, lang=lang, now=NOW),
                                 (lang, utterance))
            else:
                answer = "yes" if day.weekday() == named else "no"
                self.assertEqual(key, f"weekday_matches_date_future_{answer}", (lang, utterance))
                self.assertEqual(data["actual_weekday"], actual, (lang, utterance))

    def test_a_weekday_beside_a_date_the_parser_cannot_read_is_an_error(self):
        for lang, utterance in (("fa-IR", "۱ ژانویه پنجشنبه‌ست؟"),
                                ("fa-IR", "۳۱ اکتبر پنجشنبه میفته؟")):
            key, _ = self._slotless(utterance, lang)
            self.assertEqual(key, "extract_date_error", utterance)

    def test_questions_that_name_no_other_day_are_about_today(self):
        for lang, utterance in PLAIN_WEEKDAY_QUESTIONS:
            key, data = self._slotless(utterance, lang)
            self.assertEqual(key, "weekday_current", (lang, utterance))
            self.assertEqual(data["weekday"], nice_weekday(NOW, lang=lang), (lang, utterance))

    def test_a_time_or_a_year_beside_a_weekday_names_that_weekday(self):
        friday = date(2026, 10, 23)  # the first Friday after the pinned Saturday
        monday = date(2026, 10, 19)
        self.assertEqual((friday.weekday(), monday.weekday()), (4, 0))
        for utterance, day in (("what day is friday at 3", friday),
                               ("which date is friday at 5 pm", friday),
                               ("what date will it be on friday 2026", friday),
                               ("which day is it on monday 2027", monday)):
            key, data = self._slotless(utterance, "en-US")
            self.assertEqual(key, "weekday_at_date_future", utterance)
            self.assertEqual(data["weekday"],
                             nice_weekday(datetime.combine(day, time(12)), lang="en-US"), utterance)

    def test_a_weekday_after_next_is_not_checked_against_the_time(self):
        key, data = self._slotless("what is the date next friday at 10", "en-US")
        self.assertEqual(key, "weekday_at_date_future")
        self.assertEqual(data["weekday"], nice_weekday(datetime(2026, 10, 23), lang="en-US"))

    def test_a_danish_date_before_a_weekday_is_read_whole(self):
        # on a Thursday the parser reads "4. juli på en torsdag" as 2027-07-04, a Sunday
        thursday = self._thursday(12)
        day = date(2027, 7, 4)
        self.assertEqual(day.weekday(), 6)
        key, data = self._slotless("lander 4. juli på en torsdag", "da-DK", thursday)
        self.assertEqual(key, "weekday_at_date_future")
        self.assertEqual(data["weekday"], nice_weekday(datetime.combine(day, time(12)), lang="da-DK"))
        key, _ = self._slotless("lander 4. juli på en søndag", "da-DK", thursday)
        self.assertEqual(key, "weekday_at_date_future")

    def test_a_yes_no_question_about_a_date_the_parser_cannot_read_is_an_error(self):
        for lang, utterance in (("en-US", "will 12/25/2024 land on a friday"),
                                ("en-US", "is 12/25/2024 going to be a friday"),
                                ("en-US", "is it true that 12/25/2024 is a friday"),
                                ("en-US", "is 12/25/2024 going to be a monday"),
                                ("en-US", "is 12/25/2024 a friday"),
                                ("de-DE", "ist der 25.12.2024 ein mittwoch"),
                                ("en-US", "is 12/25/2024 a monday or a tuesday")):
            for hour in (9, 12, 21):
                key, _ = self._slotless(utterance, lang, self._thursday(hour))
                self.assertEqual(key, "extract_date_error", (lang, utterance, hour))

    def _thursday(self, hour):
        thursday = NOW.tzinfo.localize(datetime(2026, 10, 22, hour, 0))
        self.assertEqual(thursday.weekday(), 3)
        return thursday

    def test_a_time_beside_a_weekday_is_the_weekday_at_any_hour(self):
        monday = date(2026, 10, 26)
        self.assertEqual(monday.weekday(), 0)
        for lang, utterance in (("en-US", "what day is monday at 3"),
                                ("es-ES", "qué día es el lunes a las 3"),
                                ("fr-FR", "quel jour est lundi à 9h")):
            for hour in (9, 12, 16, 21):
                key, data = self._slotless(utterance, lang, self._thursday(hour))
                self.assertEqual(key, "weekday_at_date_future", (lang, utterance, hour))
                self.assertEqual(data["weekday"],
                                 nice_weekday(datetime.combine(monday, time(12)), lang=lang),
                                 (lang, utterance, hour))
                self.assertEqual(data["date"], nice_date(datetime.combine(monday, time(12)),
                                                         lang=lang, now=self._thursday(hour)),
                                 (lang, utterance, hour))

    def test_todays_month_and_day_in_another_year_is_that_date(self):
        # 2027-10-22 is a Friday; the clock is on 2026-10-22
        friday = date(2027, 10, 22)
        self.assertEqual(friday.weekday(), 4)
        for utterance in ("what day is friday october 22 2027",
                          "tell me if october 22 2027 is a friday"):
            for hour in (9, 21):
                key, data = self._slotless(utterance, "en-US", self._thursday(hour))
                self.assertEqual(key, "weekday_matches_date_future_yes", (utterance, hour))
                self.assertEqual(data["actual_weekday"], "Friday")

    def test_a_weekday_bound_as_the_date_slot_does_not_hide_the_date(self):
        # m2v binds the weekday name as the date; the date is in the rest of the text
        for lang, utterance, slot in (("pt-BR", "1º de janeiro cai numa quinta-feira", "quinta-feira"),
                                      ("pt-BR", "31 de outubro vai ser quinta-feira", "quinta-feira"),
                                      ("pt-PT", "31 de outubro calha a uma quinta-feira", "quinta-feira")):
            key, data = self._speak({"utterance": utterance, "date": slot}, lang,
                                    self._thursday(12))
            self.assertEqual(key, "weekday_matches_date_future_no", (lang, utterance))

    def test_last_and_next_before_a_weekday_and_a_time_survive_a_passed_time(self):
        def last(today, weekday):
            return today - timedelta(days=(today.weekday() - weekday) % 7 or 7)

        def next_after_tomorrow(today, weekday):
            soonest = today + timedelta(days=2)
            return soonest + timedelta(days=(weekday - soonest.weekday()) % 7)

        for today in (date(2026, 10, 22), date(2026, 10, 23), date(2026, 10, 26)):
            for hour, minute in ((21, 0), (23, 55)):
                clock = NOW.tzinfo.localize(datetime.combine(today, time(hour, minute)))
                for utterance, day in (
                        ("what day was it last monday at 9", last(today, 0)),
                        ("what date was last thursday at 8", last(today, 3)),
                        ("what was the date last friday at 3", last(today, 4)),
                        ("which date was friday at 3", last(today, 4)),
                        ("what is the date next friday at 10", next_after_tomorrow(today, 4))):
                    key, data = self._slotless(utterance, "en-US", clock)
                    expected = datetime.combine(day, time(12))
                    where = (utterance, clock.isoformat())
                    self.assertIn(key, ("weekday_at_date_past", "weekday_at_date_future"), where)
                    self.assertEqual(data["weekday"], nice_weekday(expected, lang="en-US"), where)
                    self.assertEqual(data["date"], nice_date(expected, lang="en-US", now=clock), where)


if __name__ == "__main__":
    unittest.main()
