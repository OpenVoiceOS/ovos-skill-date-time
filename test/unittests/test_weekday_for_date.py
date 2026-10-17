"""weekday_for_date answers for a date, for today, and for yes/no questions.

Each utterance is matched by padacioso against the locale's own
``weekday_for_date.intent`` and its slots go to the handler as the engine
binds them, or as none, because m2v binds no slots. "Now" is pinned to a
Saturday so the answers are fixed.
"""
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytz
from ovos_bus_client.message import Message
from ovos_date_parser import extract_datetime
from padacioso import IntentContainer

SKILL_ID = "ovos-skill-date-time.openvoiceos"
LOCALE_DIR = Path(__file__).parent.parent.parent / "locale"
NOW = pytz.timezone("Europe/Copenhagen").localize(datetime(2026, 10, 17, 12, 0))


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

    def _speak(self, data, lang):
        message = Message("weekday_for_date", data)
        with mock.patch.object(self.skill, "get_datetime", return_value=NOW), \
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

    def _slotless(self, utterance, lang="en-US"):
        """Answer when the engine binds no slot at all."""
        return self._speak({"utterance": utterance}, lang)

    def test_a_request_without_a_date_is_about_today(self):
        # 2026-10-17 is a Saturday
        for answer in (self._padacioso("what weekday is it"),
                       self._slotless("what weekday is it")):
            self.assertEqual(answer[0], "weekday_current")
            self.assertEqual(answer[1]["weekday"], "Saturday")

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

    def test_a_weekday_in_a_what_question_is_not_a_yes_no_question(self):
        key, data = self._slotless("what day of the week is next monday")
        self.assertEqual(key, "weekday_at_date_future")
        self.assertEqual(data["weekday"], "Monday")


if __name__ == "__main__":
    unittest.main()
