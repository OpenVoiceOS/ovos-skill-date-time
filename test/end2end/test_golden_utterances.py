"""Golden-utterance end-to-end coverage for ovos-skill-date-time (en-US).

Every row in ``golden_utterances.jsonl`` is a slice of the shared ovoscope
golden corpus (see /home/miro/AgentWorkspaces/knowledge/datasets/ovoscope)
for this skill's ``skill_id``. Each row is replayed through a single shared
MiniCroft boot and must route to the ``.intent`` file named by its
``intent_label``, matching the idioms in ``test_intents_en_us.py``.

A handful of utterances from OTHER skills' corpus slices are also replayed
to prove this skill does NOT claim intents that plausibly sound similar
(e.g. weather's "what time does daylight begin" vs. date-time's "what time
is it").

Run: pytest test/end2end/test_golden_utterances.py -v --timeout=120
"""
import json
import time
from pathlib import Path
from unittest import TestCase, mock

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import get_minicroft

SKILL_ID = "ovos-skill-date-time.openvoiceos"
LANG = "en-US"

PIPELINE = [
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-medium",
    "ovos-padacioso-pipeline-plugin-low",
]

GOLDEN_PATH = Path(__file__).parent / "golden_utterances.jsonl"
GOLDEN_ROWS = [
    json.loads(line)
    for line in GOLDEN_PATH.read_text().splitlines()
    if line.strip()
]

# No rows are currently xfailed. Two earlier "findings" here turned out to
# be bugs in this PR's own vendoring/tooling rather than genuine skill or
# corpus defects, both caught and fixed this round:
#
# - "is next year a leap year" / "is this year a leap year" / "is this year
#   a leap year or next" were vendored into golden_utterances.jsonl with the
#   WRONG label (next.leap.year.intent / handle_query_next_leap_year). The
#   canonical source corpus
#   (/home/miro/AgentWorkspaces/knowledge/datasets/ovoscope/test_dataset.jsonl)
#   actually labels all three against is.leap.year.intent /
#   handle_is_leap_year, matching the skill's real (and correct) behavior.
#   Re-vendored with the correct label; these now pass as ordinary rows.
# - "in something hour what time will it be" (+3 variants) were xfailed as
#   an alleged padatious {offset}-slot coverage gap ("matches no intent at
#   all"). That diagnosis was a symptom of the ".intent"-suffix
#   bus-event-name bug fixed in _assert_intent below: the utterance DOES
#   match instantly (padacioso happily binds the literal word "something"
#   into {offset}), but the old watch loop listened for an event name that
#   ovos-workshop never emits, so every row -- matched or not -- looked
#   like a timeout. Fixed listener, these now pass as ordinary rows.
XFAIL_UTTERANCES = {}

# Utterances lifted verbatim from OTHER skills' golden-corpus slices that are
# plausibly confusable with date-time phrasing (mention "time", "today", or
# scheduling). This skill must never claim them.
NEGATIVE_UTTERANCES = [
    "can you tell me the weather",
    "set an alarm",
    "set a timer",
    "what is the temperature",
    "sunrise time",
    "wake me up with music",
    "remind me to go to work weekday mornings at 8",
    "at what time does daylight begin",
]


class _FakeGeocodeResult:
    """Deterministic stand-in for ``geocoder.osm(...)`` results.

    Several golden rows carry a ``{location}`` slot (e.g. "in Africa").
    Hitting the real Nominatim/OSM endpoint from a sandboxed CI worker is
    slow and occasionally hangs past the whole-suite timeout budget (the
    skill's ``_get_timezone_from_builtins`` has no request timeout of its
    own). Intent routing does not depend on the resolved coordinates, only
    on the utterance being recognized, so the network call is stubbed out
    for determinism and speed.
    """

    ok = True
    lat = 51.5074
    lng = -0.1278


class _MiniCroftMixin:
    """Shared single-boot MiniCroft used by every test in this module."""

    @classmethod
    def setUpClass(cls):
        cls._geocoder_patch = mock.patch(
            "geocoder.osm", return_value=_FakeGeocodeResult()
        )
        cls._geocoder_patch.start()
        cls.minicroft = get_minicroft([SKILL_ID], max_wait=150)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()
        if getattr(cls, "_geocoder_patch", None):
            cls._geocoder_patch.stop()

    def _emit_and_wait(self, utterance: str, watch_msg_types, deadline_s=45, settle_s=5):
        """Emit ``utterance`` and collect any of ``watch_msg_types`` seen on the bus."""
        matched = {t: [] for t in watch_msg_types}
        handlers = {}
        for t in watch_msg_types:
            h = (lambda msg, _t=t: matched[_t].append(msg))
            handlers[t] = h
            self.minicroft.bus.on(t, h)
        try:
            session = Session(f"e2e-golden-{hash(utterance)}")
            session.lang = LANG
            session.pipeline = PIPELINE
            message = Message(
                "recognizer_loop:utterance",
                {"utterances": [utterance], "lang": LANG},
                {"session": session.serialize()},
            )
            deadline = time.monotonic() + deadline_s
            while not any(matched.values()) and time.monotonic() < deadline:
                self.minicroft.bus.emit(message)
                waited = time.monotonic() + settle_s
                while not any(matched.values()) and time.monotonic() < waited:
                    time.sleep(0.2)
        finally:
            for t, h in handlers.items():
                self.minicroft.bus.remove(t, h)
        return matched

    def _assert_intent(self, utterance: str, intent_file: str):
        # ovos_workshop.intents strips a trailing ".intent" suffix off the
        # registered intent name before it ever reaches the bus (see
        # IntentServiceInterface._normalize_name in ovos-workshop), so the
        # dispatched message type is "<skill_id>:<name-without-.intent>",
        # never "<skill_id>:<name>.intent". Listening on the raw
        # intent_label (which keeps the corpus's ".intent" suffix) means the
        # handler below is registered for an event that is never emitted --
        # the golden row silently "times out" even though the correct
        # IntentHandlerMatch fires instantly and repeatedly on every retry.
        intent_name = intent_file[:-len(".intent")] if intent_file.endswith(".intent") else intent_file
        intent_msg_type = f"{SKILL_ID}:{intent_name}"
        matched = self._emit_and_wait(utterance, [intent_msg_type])
        self.assertTrue(
            matched[intent_msg_type],
            f"{utterance!r} did not route to {intent_file}",
        )

    def _assert_not_claimed(self, utterance: str):
        """Assert this skill's intents never fire for ``utterance``."""
        skill_intents = [
            f"{SKILL_ID}:{row['intent_label'][:-len('.intent')] if row['intent_label'].endswith('.intent') else row['intent_label']}"
            for row in {r["intent_label"]: r for r in GOLDEN_ROWS}.values()
        ]
        matched = self._emit_and_wait(
            utterance, skill_intents, deadline_s=15, settle_s=4
        )
        fired = [t for t, msgs in matched.items() if msgs]
        self.assertFalse(
            fired,
            f"{utterance!r} unexpectedly routed to {fired} (should not be "
            f"claimed by {SKILL_ID})",
        )


class TestGoldenUtterances(_MiniCroftMixin, TestCase):
    """Every row of the vendored golden corpus must route to its intent."""


def _make_golden_test(row):
    def _test(self):
        self._assert_intent(row["utterance"], row["intent_label"])

    _test.__name__ = f"test_golden_{row['intent_label']}_{hash(row['utterance']) & 0xffffffff:x}"
    xfail_reason = XFAIL_UTTERANCES.get(row["utterance"])
    if xfail_reason:
        _test = pytest.mark.xfail(strict=True, reason=xfail_reason)(_test)
    return _test


for _i, _row in enumerate(GOLDEN_ROWS):
    _name = f"test_row_{_i:03d}_{_row['intent_label'].replace('.', '_')}"
    setattr(TestGoldenUtterances, _name, _make_golden_test(_row))


# Negative tests share the SAME class (and therefore the same single
# MiniCroft boot) as the golden-row tests above, rather than paying for a
# second class-level boot: this suite already adds one boot on top of the
# five in test_intents_en_us.py, and CI runs all end2end classes under
# pytest-xdist, so keeping the boot count minimal avoids starving sibling
# workers past MiniCroft's READY-state timeout.
def _make_negative_test(utterance):
    def _test(self):
        self._assert_not_claimed(utterance)

    _test.__name__ = f"test_negative_{hash(utterance) & 0xffffffff:x}"
    return _test


for _i, _utt in enumerate(NEGATIVE_UTTERANCES):
    _name = f"test_neg_{_i:02d}"
    setattr(TestGoldenUtterances, _name, _make_negative_test(_utt))
