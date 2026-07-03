"""End-to-end coverage for the en-US date/time intent definitions.

A MiniCroft loads the real skill plugin, so the assertions exercise the same
resource loading and intent registration path used at runtime. Utterance
matching is checked against the trained Padacioso container the skill registers
its ``.intent`` samples into, which yields the intent name deterministically.

Only location-free utterances are used, so no network geocoding is required.
"""
from unittest import TestCase

from ovoscope import get_minicroft

SKILL_ID = "ovos-skill-date-time.openvoiceos"
LANG = "en-US"


class TestDateTimeIntents(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID])
        cls.container = cls.minicroft.intents.pipeline_plugins[
            "ovos-padacioso-pipeline-plugin"
        ].containers[LANG]

    @classmethod
    def tearDownClass(cls):
        if cls.minicroft:
            cls.minicroft.stop()

    def test_en_us_datetime_intents(self):
        self.assertIn(SKILL_ID, self.minicroft.plugin_skills)

        cases = {
            "what time is it": "what.time.is.it.intent",
            "what date is it": "current_date.intent",
            "what day is it": "what.day.is.it.intent",
            "what weekday is it": "what.weekday.is.it.intent",
            "what month is it": "what.month.is.it.intent",
            "what year are we in": "what.year.is.it.intent",
        }
        for utterance, intent_file in cases.items():
            intent = f"{SKILL_ID}:{intent_file}"
            self.assertIn(intent, self.container.intent_samples, intent_file)
            match = self.container.calc_intent(utterance)
            self.assertEqual(match["name"], intent, utterance)
