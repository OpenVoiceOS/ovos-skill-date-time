"""Unit coverage that initialize() actually wires the {location}/{date}/
{weekday}/{offset} slots to their locale/*/*.entity files via
self.register_entity_file(). This is the deterministic half of the
entity-registration regression check: the end2end suite
(test/end2end/test_entity_constraints.py) shows the routing-level effect of
the registered hints; this test shows the wiring itself is present and
survived any future refactor of initialize().

Red-before-green-after: with register_entity_file() commented out of
initialize() (the pre-fix state, matching every ovos-skill-date-time release
before this PR), this test fails with an empty call list -- there is no
scenario where it accidentally passes on the old code.
"""
import unittest
from os.path import dirname
from unittest import mock

from ovos_utils.messagebus import FakeBus
from ovos_skill_date_time import TimeSkill


class TestEntityRegistration(unittest.TestCase):

    def test_initialize_registers_all_slot_entity_files(self):
        bus = FakeBus()
        skill = TimeSkill()
        with mock.patch.object(
            TimeSkill, "register_entity_file", autospec=True
        ) as mocked:
            skill._startup(bus, "ovos-skill-date-time.openvoiceos")
        registered = {call.args[1] for call in mocked.call_args_list}
        self.assertEqual(
            registered,
            {"location.entity", "date.entity", "weekday.entity", "offset.entity"},
            "initialize() should register an entity file for every "
            "{slot} that has one under locale/*/",
        )
