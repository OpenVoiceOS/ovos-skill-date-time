"""Regression test: date-time must not steal "is there a gpu in your
system" from ovos-skill-diagnostics under the REAL default pipeline.

Root cause (pre-fix): ``locale/en-US/intents/weekday.matches.date.intent``
carried two bare, unqualified samples --

    is {date} a {weekday}
    was {date} a {weekday}

-- whose only fixed tokens are "is"/"was" + "a", four tokens total. Padatious
scores structural overlap, not entity-membership; the fixed tokens "is"/"a"
(or "was"/"a") land in exactly the right positions for "is there a gpu in
your system" (is=is, {date}=there, a=a, {weekday}='gpu in your system'), so
the template matched at ovos-padatious-pipeline-plugin-high confidence
(> 0.95) and won the turn away from ovos-skill-diagnostics' query_gpu intent
-- even though neither slot's filler is a real date or weekday.

The fix drops those two bare lines, keeping only the "on"-qualified /
"fall on" phrasings ("is {date} on a {weekday}", "was {date} on a
{weekday}", "does {date} fall on a {weekday}", "will {date} be on a
{weekday}"), which do not structurally collide with "is there a gpu in your
system" style utterances.

This test boots a two-skill MiniCroft (date-time + diagnostics) under the
REAL OVOS default pipeline (see
/home/miro/AgentWorkspaces/ovos/core/ovos-config/ovos_config/mycroft.conf
lines ~218-231 -- NOT ovoscope's broader DEFAULT_TEST_PIPELINE constant) and
asserts date-time's weekday.matches.date intent no longer claims the
utterance.

Run: pytest test/end2end/test_gpu_overmatch_regression.py -v --timeout=150
"""
import os
import tempfile
import time
from unittest import TestCase

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import get_minicroft

INTENT_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "locale", "en-US", "intents", "weekday.matches.date.intent")

DATE_TIME_SKILL_ID = "ovos-skill-date-time.openvoiceos"
DIAGNOSTICS_SKILL_ID = "ovos-skill-diagnostics.openvoiceos"
LANG = "en-US"

# The non-media-plugin-dependent subset of the REAL default pipeline from
# mycroft.conf (NOT ovoscope's broader DEFAULT_TEST_PIPELINE). The full real
# default additionally includes ovos-ocp-pipeline-plugin-{high,medium} and
# ovos-m2v-pipeline-high, but neither date-time nor diagnostics register any
# OCP/media or model2vec intents for this utterance, and those plugins are
# not installed as test dependencies of this repo's CI. What matters here --
# and what this list preserves from the real default -- is the exclusion of
# padatious-low / adapt-low / padacioso, present in ovoscope's broader test
# constant but not in a real default OVOS install.
REAL_DEFAULT_PIPELINE = [
    "ovos-stop-pipeline-plugin-high",
    "ovos-converse-pipeline-plugin",
    "ovos-padatious-pipeline-plugin-high",
    "ovos-adapt-pipeline-plugin-high",
    "ovos-fallback-pipeline-plugin-high",
    "ovos-stop-pipeline-plugin-medium",
    "ovos-adapt-pipeline-plugin-medium",
    "ovos-fallback-pipeline-plugin-medium",
    "ovos-fallback-pipeline-plugin-low",
]

UTTERANCE = "is there a gpu in your system"

# date-time's own weekday.matches.date intent event, the thing that used to
# fire (falsely) for this utterance.
DATE_TIME_EVENT = f"{DATE_TIME_SKILL_ID}:weekday.matches.date"


class TestGpuOvermatchEngineLevel(TestCase):
    """Fast, deterministic root-cause proof at the padatious-engine level
    (no MiniCroft boot): before the fix, "is there a gpu in your system"
    scores confidence 1.0 against weekday.matches.date (a bare "is {date}
    a {weekday}" sample structurally matches it token-for-token); after
    dropping the two bare unqualified samples, confidence drops to ~0.52,
    well below what any padatious-high tier treats as a winning match.
    """

    def test_confidence_no_longer_near_perfect(self):
        # not a declared test dependency of this repo (the padatious
        # engine is normally reached only indirectly, via the
        # ovos-padatious-pipeline-plugin entry point installed for the
        # MiniCroft-based test below) -- skip gracefully rather than
        # erroring test collection if it isn't importable in this env.
        padatious = pytest.importorskip("ovos_padatious")
        with tempfile.TemporaryDirectory() as cache:
            c = padatious.IntentContainer(cache)
            c.load_intent("weekday_matches_date", INTENT_FILE)
            c.train()
            data = c.calc_intent("is there a gpu in your system")
            self.assertLess(
                data.conf, 0.8,
                f"weekday.matches.date still near-perfectly matches the "
                f"GPU utterance (conf={data.conf}); over-general sample(s) "
                f"not fully removed")


class TestGpuOvermatchRegression(TestCase):
    """date-time must not claim a diagnostics-owned utterance."""

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft(
            [DATE_TIME_SKILL_ID, DIAGNOSTICS_SKILL_ID], max_wait=150,
            default_pipeline=REAL_DEFAULT_PIPELINE,
        )

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def test_date_time_does_not_claim_gpu_utterance(self):
        matched = []
        handler = lambda msg: matched.append(msg)
        self.minicroft.bus.on(DATE_TIME_EVENT, handler)
        try:
            session = Session("e2e-gpu-overmatch-regression")
            session.lang = LANG
            session.pipeline = REAL_DEFAULT_PIPELINE
            message = Message(
                "recognizer_loop:utterance",
                {"utterances": [UTTERANCE], "lang": LANG},
                {"session": session.serialize()},
            )
            # Give date-time's padatious matcher every chance to (wrongly)
            # fire: re-emit and settle repeatedly, same idiom as the other
            # end2end suites in this directory.
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                self.minicroft.bus.emit(message)
                waited = time.monotonic() + 5
                while time.monotonic() < waited:
                    time.sleep(0.2)
                if matched:
                    break
        finally:
            self.minicroft.bus.remove(DATE_TIME_EVENT, handler)

        self.assertFalse(
            matched,
            f"{UTTERANCE!r} unexpectedly routed to {DATE_TIME_EVENT} "
            "(date-time is over-matching a diagnostics-owned utterance again)",
        )
