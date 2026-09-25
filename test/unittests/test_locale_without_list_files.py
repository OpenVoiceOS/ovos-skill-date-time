"""A locale that ships no `.list` file must still answer a located query.

`SkillResources.load_list_file` returns None, not an empty list, when the
locale has no such file. `_load_locale_phrase_set` iterated that return
value directly, so the first located query in such a locale raised
TypeError inside the intent handler and the skill spoke `skill.error`.

Adding the files to a locale is a localization task. Surviving their
absence is this skill's, because a user can set a language the skill
ships no locale for at all.
"""
import unittest

from ovos_utils.messagebus import FakeBus

from ovos_skill_date_time import TimeSkill

SKILL_ID = "ovos-skill-date-time.openvoiceos"

#: The skill ships no `locale/ja-JP`, so every list file is absent there.
LOCALE_WITHOUT_LISTS = "ja-JP"
#: en-US ships all three, and is the positive control: the same helper must
#: return a populated set there, or "it returned an empty set" would prove
#: nothing.
LOCALE_WITH_LISTS = "en-US"


class TestALocaleWithoutListFilesStillAnswers(unittest.TestCase):

    def _skill(self, lang):
        skill = TimeSkill()
        skill._startup(FakeBus(), SKILL_ID)
        skill.config_core["lang"] = lang
        skill._lang = lang
        # `resources` is built per language; drop the cached one so the
        # next read is against `lang`.
        skill._resources = None
        skill.resources.static.clear()
        return skill

    def test_the_phrase_set_is_empty_not_a_typeerror(self):
        skill = self._skill(LOCALE_WITHOUT_LISTS)
        for name in ("ambiguous_locations", "non_location_phrases",
                     "current_weekend_phrases"):
            with self.subTest(list_file=name):
                self.assertEqual(skill._load_locale_phrase_set(name), set())

    def test_the_positive_control_loads_a_populated_set(self):
        # Without this, an empty set proves only that the helper ran.
        skill = self._skill(LOCALE_WITH_LISTS)
        self.assertGreater(
            len(skill._load_locale_phrase_set("ambiguous_locations")), 0)

    def test_a_located_query_resolves_instead_of_raising(self):
        # The path the live probe took: a location reaches `_resolve_location`
        # and both list-backed helpers run on it.
        skill = self._skill(LOCALE_WITHOUT_LISTS)
        self.assertEqual(skill._resolve_location("Praha"), "Praha")
        self.assertFalse(skill._is_ambiguous_location("Praha"))
        self.assertFalse(skill._mentions_current_weekend("what day is it"))

    def test_the_control_locale_still_marks_its_ambiguous_names(self):
        # The second control: the fallback must not turn a locale that HAS
        # the file into one that marks nothing.
        skill = self._skill(LOCALE_WITH_LISTS)
        marked = skill._load_locale_phrase_set("ambiguous_locations")
        self.assertTrue(
            any(skill._is_ambiguous_location(name) for name in marked))


if __name__ == "__main__":
    unittest.main()
