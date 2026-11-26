"""The en-us time_until templates must not catch questions that name no date.

A template whose {date} slot follows only a generic question stem ("when was
{date}", "how far away is {date}") binds any noun phrase, so "when was the
eiffel tower built" reached the handler with date="the eiffel tower built".
The templates are loaded into padacioso, the template matcher the test extras
already ship, so these cases check the template lines themselves.
"""
import unittest
from pathlib import Path

from padacioso import IntentContainer

INTENT_FILE = (Path(__file__).parent.parent.parent / "locale" / "en-US"
               / "intents" / "time_until.intent")


def _container():
    lines = [line.strip() for line in INTENT_FILE.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.startswith("#")]
    container = IntentContainer()
    container.add_intent("time_until", lines)
    return container


class TestTimeUntilTemplates(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.container = _container()

    def _matched(self, utterance):
        return self.container.calc_intent(utterance).get("name") == "time_until"

    def test_questions_that_name_no_date_do_not_match(self):
        for utterance in ("when was the eiffel tower built",
                          "how far away is the moon",
                          "how far off is the moon from here",
                          "when is the meeting with bob",
                          "when will it be my turn"):
            with self.subTest(utterance=utterance):
                self.assertFalse(self._matched(utterance))

    def test_questions_that_ask_for_a_distance_still_match(self):
        for utterance in ("how many days are left until christmas",
                          "how long ago was new years day",
                          "how much time is left until halloween",
                          "when is the next friday",
                          "when was the last monday"):
            with self.subTest(utterance=utterance):
                self.assertTrue(self._matched(utterance))

    def test_bare_holiday_questions_still_match(self):
        # the holidays are listed by name, so "when is" stays closed to other noun phrases
        for utterance in ("when is christmas",
                          "when's halloween",
                          "when was easter",
                          "when is new year's day",
                          "when is mother's day"):
            with self.subTest(utterance=utterance):
                self.assertTrue(self._matched(utterance))


if __name__ == "__main__":
    unittest.main()
