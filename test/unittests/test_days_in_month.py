"""Routing and handler tests for the days-in-month intent.

Intent routing is exercised with the pure-python padacioso engine so the
tests run offline. The intent carries a ``{month}`` slot filled from
``month.entity``.
"""
import unittest
from os.path import dirname, join

from ovos_bus_client.message import Message
from ovos_utils.messagebus import FakeBus
from padacioso import IntentContainer

from ovos_skill_date_time import TimeSkill

LOCALE = join(dirname(dirname(dirname(__file__))), "locale", "en-US")


def _load_lines(path):
    with open(path, encoding="utf-8") as handle:
        return [line.strip() for line in handle
                if line.strip() and not line.startswith("#")]


class TestDaysInMonthRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.container = IntentContainer()
        cls.container.add_entity("month", _load_lines(join(LOCALE, "month.entity")))
        cls.container.add_intent(
            "days_in_month",
            _load_lines(join(LOCALE, "intents", "days_in_month.intent")))

    def test_extracts_full_month_slot(self):
        match = self.container.calc_intent("how many days in february")
        self.assertEqual(match["name"], "days_in_month")
        self.assertEqual(match["entities"].get("month"), "february")

    def test_extracts_abbreviated_month_slot(self):
        match = self.container.calc_intent("how many days does sept have")
        self.assertEqual(match["name"], "days_in_month")
        self.assertEqual(match["entities"].get("month"), "sept")


class TestDaysInMonthHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = TimeSkill()
        cls.skill._startup(FakeBus(), "ovos-skill-date-time.openvoiceos")

    def _capture(self, month_name):
        captured = {}

        def _fake_speak(dialog, data=None, *args, **kwargs):
            captured["dialog"] = dialog
            captured["data"] = data or {}

        original = self.skill.speak_dialog
        self.skill.speak_dialog = _fake_speak
        try:
            self.skill.handle_days_in_month(
                Message("test", {"month": month_name}))
        finally:
            self.skill.speak_dialog = original
        return captured

    def test_resolve_month_number(self):
        self.assertEqual(self.skill._resolve_month_number("February"), 2)
        self.assertEqual(self.skill._resolve_month_number("sept"), 9)
        self.assertIsNone(self.skill._resolve_month_number("notamonth"))

    def test_february_days(self):
        captured = self._capture("february")
        self.assertEqual(captured["dialog"], "days_in_month")
        self.assertIn(captured["data"]["num_days"], (28, 29))

    def test_april_has_thirty_days(self):
        captured = self._capture("april")
        self.assertEqual(captured["dialog"], "days_in_month")
        self.assertEqual(captured["data"]["num_days"], 30)

    def test_unknown_month_errors(self):
        captured = self._capture("smarch")
        self.assertEqual(captured["dialog"], "extract.date.error")

    def test_empty_month_errors(self):
        captured = self._capture("")
        self.assertEqual(captured["dialog"], "extract.date.error")


if __name__ == "__main__":
    unittest.main()
