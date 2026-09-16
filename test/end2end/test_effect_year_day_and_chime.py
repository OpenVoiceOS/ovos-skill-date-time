"""Effect-checking end-to-end coverage for ovos-skill-date-time.

``test_intents_en_us.py`` and ``test_intents_it_it.py`` only assert that an
utterance routed to the expected ``.intent`` handler -- a handler that
matched and then spoke nothing would still pass. This suite drives the same
real MiniCroft bus and asserts the actual consequence:

- "what year is it" (en-US) must speak the ``year.current`` dialog with the
  actual current year, computed by the test with ``nice_year`` and not read
  back from the skill.
- "che giorno del mese è oggi" (it-IT, ``what.day.is.it.intent``) must speak
  the ``day.current`` dialog with exactly today's rendered day, exercising
  the skill's it-IT locale -- a default en-US boot only registers en-US intents.

Both expectations use ``ovos_utils.time.now_local()``, the configured-timezone
clock the handler renders with (``get_datetime`` -> ``now_local(tz)``). A naive
``datetime.now()`` is the host clock: on a UTC host with the default
America/Chicago configuration it is a day ahead from 00:00 to 05:00 UTC.
- the hourly chime is genuinely clock-driven: ``initialize()`` calls
  ``self.schedule_event(self._handle_play_hour_chime, ...)``.
  ``get_minicroft`` defaults ``enable_event_scheduler=False``
  (ovoscope/__init__.py:458), under which ``ovos_core.skill_manager.
  SkillManager`` never constructs an ``event_scheduler`` at all, so any
  scheduled-event assertion would be vacuous. This suite passes
  ``enable_event_scheduler=True``, reads the schedule the skill registered
  for itself during ``initialize()``, then invokes the same real handler
  and asserts the ``mycroft.audio.play_sound`` message it emits carries the
  configured chime file.
"""
import os
import time

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovos_bus_client.util.scheduled_events.legacy import pending_migration_path
from ovos_bus_client.util.scheduled_events.store import default_store_path
from ovos_date_parser import nice_day, nice_year
from ovos_utils.time import now_local
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-date-time.openvoiceos"

PIPELINE = [
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-medium",
    "ovos-padacioso-pipeline-plugin-low",
]


def _speak_dialog(mc, utterance, lang, session_id):
    session = Session(session_id)
    session.lang = lang
    session.pipeline = list(PIPELINE)
    msg = Message(
        "recognizer_loop:utterance",
        {"utterances": [utterance], "lang": lang},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(mc, eof_msgs=["ovos.utterance.handled"])
    capture.capture(msg, timeout=30)
    messages = capture.finish()
    speaks = [m for m in messages if m.msg_type in ("speak", "ovos.utterance.speak")]
    assert speaks, f"{utterance!r}: no speak message emitted, got {[m.msg_type for m in messages]!r}"
    return speaks[0]


def test_current_year_speaks_actual_year_en_us():
    mc = get_minicroft([SKILL_ID], max_wait=150)
    try:
        speak = _speak_dialog(mc, "what year is it", "en-US", "e2e-year-en")
        meta = speak.data["meta"]
        assert meta["dialog"] == "year.current", (
            f"expected year.current, got {meta['dialog']!r}"
        )
        expected_year = nice_year(now_local(), lang="en-US")
        assert meta["data"]["year"] == expected_year, (
            f"expected year {expected_year!r}, got {meta['data']!r}"
        )
    finally:
        mc.stop()


def test_current_day_of_month_it_it():
    mc = get_minicroft([SKILL_ID], lang="it-IT", max_wait=150)
    try:
        speak = _speak_dialog(
            mc, "che giorno del mese è oggi", "it-IT", "e2e-day-it"
        )
        meta = speak.data["meta"]
        assert meta["dialog"] == "day.current", (
            f"expected day.current, got {meta['dialog']!r}"
        )
        expected_day = nice_day(now_local(), lang="it-IT")
        assert meta["data"]["day"] == expected_day, (
            f"expected day {expected_day!r}, got {meta['data']!r}"
        )
    finally:
        mc.stop()


def test_hourly_chime_is_registered_with_a_live_scheduler_and_plays_audio():
    """Boots with enable_event_scheduler=True (default False leaves any
    scheduled-event assertion vacuous: with no live scheduler behind it,
    schedule_event() has nothing to register with and a status query can
    only ever answer "not scheduled").

    Two things are asserted against the real objects this produces:

    1. The skill scheduled its own chime: ``initialize()`` calls
       ``_schedule_hour_chime()``, and the test reads the scheduler's own
       ``schedules`` dict for that entry without scheduling anything itself
       (``mc.event_scheduler`` is the ``ScheduledEventService`` instance
       ``ovos_core.skill_manager.SkillManager`` constructs only when
       ``enable_event_scheduler=True``; it is ``None`` otherwise). A skill
       that never calls ``_schedule_hour_chime()`` fails here.
    2. The effect is real: invoking the same real handler that the
       scheduler holds a reference to speaks the chime audio via the
       genuine ``mycroft.audio.play_sound`` bus message, with the payload's
       ``uri`` checked against the skill's own configured chime file.

    (A background-thread "wait for the real tick to fire" version of this
    test passed locally but proved flaky on CI's slower runner -- the
    registration check above is what actually needs a live scheduler; the
    handler's own effect does not need waiting for a timer to prove.)

    The scheduler loads its saved schedules before the skill's
    ``initialize()`` runs, and the conftest reuses one state dir per worker.
    An entry saved by an earlier run would satisfy check 1 for a skill that
    schedules nothing, so the saved store is removed before boot, together
    with the configuration-directory store the scheduler would otherwise
    migrate into it.
    """
    for stale in (default_store_path(), pending_migration_path()):
        if stale and os.path.isfile(stale):
            os.remove(stale)
    mc = get_minicroft([SKILL_ID], max_wait=150, enable_event_scheduler=True)
    try:
        skill = mc.plugin_skills[SKILL_ID].instance
        skill.settings["play_hour_chime"] = True

        assert mc.event_scheduler is not None, (
            "MiniCroft has no event_scheduler at all -- "
            "enable_event_scheduler=True should have constructed one"
        )

        # The skill's initialize() scheduled the chime over the real bus;
        # ScheduledEventService derives the schedule name from the handler
        # (observed key: (skill_id, "_handle_play_hour_chime")). The
        # registration is asynchronous, so poll briefly. The test schedules
        # nothing itself, so any entry found is the skill's own.
        registered = []
        deadline = time.monotonic() + 10
        while not registered and time.monotonic() < deadline:
            registered = [
                key for key in mc.event_scheduler.schedules
                if key[0] == SKILL_ID and "_handle_play_hour_chime" in key[1]
            ]
            if not registered:
                time.sleep(0.2)
        assert registered, (
            f"the skill did not schedule _handle_play_hour_chime with the live "
            f"EventScheduler, got keys {list(mc.event_scheduler.schedules)!r}"
        )

        played = []
        mc.bus.on("mycroft.audio.play_sound", lambda m: played.append(m))
        skill._handle_play_hour_chime(Message("e2e-chime-invoke"))

        assert played, "mycroft.audio.play_sound was never emitted by the chime handler"
        assert played[0].data["uri"] == skill.hour_chime, (
            f"expected chime file {skill.hour_chime!r}, got {played[0].data!r}"
        )
    finally:
        mc.stop()
