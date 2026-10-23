# Copyright 2017, Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import calendar
import datetime
import os
import re
import unicodedata
from typing import Iterable, Optional

import geocoder
import pytz
from ovos_bus_client.message import Message
from ovos_date_parser import nice_time, extract_datetime, nice_date, nice_duration, date_time_format, nice_weekday, \
    nice_month, nice_day, nice_year, extract_holiday_date
from ovos_utils import classproperty
from ovos_utils.log import LOG
from ovos_utils.parse import fuzzy_match
from ovos_utils.process_utils import RuntimeRequirements
from ovos_utils.time import now_local, get_next_leap_year
from ovos_utterance_normalizer import UtteranceNormalizerPlugin
from ovos_spec_tools.expansion import expand
from ovos_workshop.decorators import intent_handler
from ovos_workshop.resource_files import ResourceFile
from ovos_workshop.skills import OVOSSkill
from timezonefinder import TimezoneFinder


def speakable_timezone(tz):
    """Convert a timezone string to a more speakable form.

    This function reformats a timezone string by:
      - Inserting spaces between camel case words (e.g., 'EasterIsland' → 'Easter Island')
      - Replacing underscores with spaces
      - Reversing the components of a timezone path (e.g., 'America/North_Dakota/Center' → 'Center North Dakota America')

    Args:
        tz (str): A timezone string in pytz format.

    Returns:
        str: A more natural, speakable form of the timezone.
    """
    say = re.sub(r"([a-z])([A-Z])", r"\g<1> \g<2>", tz)
    say = say.replace("_", " ")
    say = say.split("/")
    say.reverse()
    return " ".join(say)


class TimeSkill(OVOSSkill):
    """A skill for interacting with date and time information."""

    @classproperty
    def runtime_requirements(self):
        """this skill does not need internet"""
        return RuntimeRequirements(internet_before_load=False,
                                   network_before_load=False,
                                   gui_before_load=False,
                                   requires_internet=False,
                                   requires_network=False,
                                   requires_gui=False,
                                   no_internet_fallback=True,
                                   no_network_fallback=True,
                                   no_gui_fallback=True)

    def initialize(self):
        """Initialize the skill by pre-loading language settings and scheduling
        the hourly chime.

        This method is called automatically when the skill starts, preloading
        language-related formatting for date and time and setting up the initial
        scheduling for the hourly chime event.
        """
        date_time_format.cache(self.lang)
        self._schedule_hour_chime()

    def _handle_play_hour_chime(self, message: Message):
        """Play the hourly chime audio and re-schedule the next chime event.

        Args:
            message (Message): message object

        This method checks if the hourly chime setting is enabled. If it is, it
        plays the specified chime audio. Then, it re-schedules the next hourly
        chime event.
        """
        if self.play_hour_chime:
            self.play_audio(self.hour_chime, instant=True)
        self._schedule_hour_chime()

    def _schedule_hour_chime(self):
        """Schedule the next hourly chime event for the start of the next hour.

        This method calculates the time for the upcoming hour, setting it as
        the scheduled time for the next chime event.
        """
        n = now_local() + datetime.timedelta(hours=1)
        self.schedule_event(self._handle_play_hour_chime,
                            when=datetime.datetime(year=n.year, month=n.month, day=n.day,
                                                   hour=n.hour, minute=0, second=0))

    @property
    def play_hour_chime(self) -> bool:
        """Check if the hourly chime setting is enabled.

        Returns:
            bool: True if the chime should be played on the hour, False otherwise.
        """
        return self.settings.get("play_hour_chime", False)

    @property
    def hour_chime(self) -> str:
        """Get the file path for the hourly chime sound.

        Returns:
            str: The file path to the chime audio file. If not set in settings,
            defaults to 'casio-watch.wav' in the 'res' folder.
        """
        snd = self.settings.get("hour_sound", "casio-watch.wav")
        if not os.path.isfile(snd):
            snd2 = f"{os.path.dirname(__file__)}/res/{snd}"
            snd = snd2 if os.path.isfile(snd2) else snd
        return snd

    @property
    def use_24hour(self):
        """Determine if 24-hour time format is used.

        Returns:
            bool: True if using 24-hour format, False otherwise.
        """
        return self.time_format == 'full'

    @staticmethod
    def _normalize_phrase(text: str) -> str:
        """Normalize phrases for case-insensitive locale resource matching."""
        return text.strip(" \t,;:.!?").casefold()

    def _load_locale_phrase_set(self, name: str):
        """Load a locale phrase list once and return a normalized set.

        `load_list_file` returns None, not an empty list, when the locale
        ships no such `.list` file. Iterating that raised TypeError inside
        the intent handler, so a located query in such a locale spoke
        `skill.error` instead of answering. An empty set means the locale
        marks no phrase, which is what the callers already handle.
        """
        cache_key = f"{name}.list.normalized"
        if cache_key not in self.resources.static:
            self.resources.static[cache_key] = {
                self._normalize_phrase(phrase)
                for phrase in (self.resources.load_list_file(name) or [])
                if phrase.strip()
            }
        return self.resources.static[cache_key]

    ######################################################################
    # parsing
    def _is_ambiguous_location(self, location_string: str) -> bool:
        """Return True when a locale marks a location name as timezone-ambiguous."""
        return (
            self._normalize_phrase(location_string)
            in self._load_locale_phrase_set("ambiguous_locations")
        )

    def _sanitize_location(self, location_string: Optional[str]) -> Optional[str]:
        """Discard locale-specific phrases accidentally captured as locations."""
        if not location_string:
            return None
        cleaned = location_string.strip(" \t,;:.!?")
        if (
            self._normalize_phrase(cleaned)
            in self._load_locale_phrase_set("non_location_phrases")
        ):
            return None
        return cleaned

    def _resolve_location(self,
                          location_string: Optional[str] = None) -> Optional[str]:
        """Resolve a sanitized location from the intent's {location} slot.

        The slot is the only source. The skill used to fall back on a
        per-locale `location.rx`, which ovos-workshop deprecates. That file
        also could not work in every locale it shipped: the cs-CZ patterns
        named English prepositions and malformed the named group, and the
        hu-HU alternation let a match carry no `Location` group, which
        raised AttributeError inside the handler.
        """
        return self._sanitize_location(location_string)

    def _mentions_current_weekend(self, utterance: str) -> bool:
        """Check whether the active locale explicitly asked for the current weekend."""
        current_weekend_phrases = self._load_locale_phrase_set("current_weekend_phrases")
        if not current_weekend_phrases:
            return False
        normalized_utterance = utterance.casefold()
        return any(phrase in normalized_utterance for phrase in current_weekend_phrases)

    def _load_cached_entity(self, name: str):
        """Load and cache a locale entity resource."""
        cache_key = f"{self.lang}:{name}.entity"
        if cache_key not in self.resources.static:
            entity_resource = ResourceFile(self.resources.types.entity, name)
            values = []
            if entity_resource.file_path:
                with open(entity_resource.file_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            values.append(line)
            self.resources.static[cache_key] = values
        return self.resources.static[cache_key]

    @staticmethod
    def _fold(text: str) -> str:
        """Casefold and strip accents, one character for one, so spans hold."""
        return "".join(unicodedata.normalize("NFD", char)[0] for char in text.casefold())

    @classmethod
    def _weekday_pattern(cls, name: str) -> str:
        """Regex for a weekday name; the engine may split a hyphen off.

        Persian writes a name like "yekshanbe" with a zero-width non-joiner
        or a space between its letters, and the utterance normalizer turns
        the joiner into a space, so either may sit between two Arabic letters.
        """
        hyphen = r"\s*-\s*"
        words = []
        for part in cls._fold(name).replace("\u200c", "").split("-"):
            word = re.escape(part[:1])
            for before, char in zip(part, part[1:]):
                arabic = all(unicodedata.name(c, "").startswith("ARABIC") for c in (before, char))
                word += ("[\u200c ]?" if arabic else "") + re.escape(char)
            words.append(word)
        return r"(?<!\w)" + hyphen.join(words) + r"(?!\w)"

    def _blank_weekday_questions(self, text: str) -> str:
        """Blank the phrases that ask for the weekday.

        The locale lists them in weekday_question_phrases.list: a weekday's
        name or the word "week" in them is part of the question, not a day or
        a week the user names.
        """
        for phrase in sorted(self._load_locale_phrase_set("weekday_question_phrases"),
                             key=len, reverse=True):
            text = re.sub(rf"(?<!\w){re.escape(phrase)}(?!\w)",
                          lambda match: " " * len(match.group()), text,
                          flags=re.IGNORECASE)
        return text

    def _find_named_weekdays(self, utterance: str):
        """Return the (index, span) of every weekday the utterance names.

        Names match without accents: a speaker may leave them out of a name
        the entity file spells with them.
        """
        folded = self._fold(self._blank_weekday_questions(utterance))
        found = [(index, match.span())
                 for index, name in enumerate(self._load_cached_entity("weekday"))
                 for match in re.finditer(self._weekday_pattern(name), folded)]
        # a name inside a longer name is not named: "shanbe" in "yek-shanbe"
        return sorted(
            (named for named in found
             if not any(other != named and other[1][0] <= named[1][0]
                        and named[1][1] <= other[1][1] for other in found)),
            key=lambda named: named[1])

    def _is_yes_no_question(self, utterance: str) -> bool:
        """Check whether the utterance asks a yes/no question about a weekday.

        A request that holds a question word ("what", "welcher") asks for a
        weekday, whatever else it holds. Otherwise the question opens with a
        yes/no word, or closes with one in a language that ends a question
        with its marker.
        """
        if self.voc_match(utterance, "question_word", lang=self.lang):
            return False
        words = utterance.casefold().split()
        if not words:
            return False
        return (self.voc_match(" ".join(words[:2]), "yes_no_indicator",
                               lang=self.lang)
                or self.voc_match(words[-1], "yes_no_closer", lang=self.lang))

    def _parse_date(self, text: str, now):
        """Return the first date in the text, or None.

        The parser can leave a date expression half read when an article opens
        it ("a week from today"). Each article that precedes another word is
        also tried as the number 1, and the reading that leaves the least text
        unread wins. An article that the request lines themselves put before
        those two words ("the week is" of "what day of the week is it") is
        request wording, not a number.
        """
        words = text.split()
        request_triples = self._request_triples()
        candidates = [text] + [
            " ".join(words[:i] + ["1"] + words[i + 1:])
            for i, word in enumerate(words[:-1])
            if self.voc_match(word, "date_article", lang=self.lang)
            and tuple((self._tokens(" ".join(words[i:i + 3])) + ["$"])[:3]) not in request_triples]
        best = None
        for candidate in candidates:
            try:
                found = extract_datetime(candidate, anchorDate=now,
                                         lang=self.lang)
            except Exception:
                self.log.exception(f"failed to extract date from '{candidate}'")
                continue
            if found and found[0]:
                unread = len((found[1] or "").split())
                if best is None or unread < best[0]:
                    best = (unread, found[0])
        return best[1] if best else None

    def _tokens(self, text: str) -> list:
        text = text.replace("\u2019", "'")
        return [token for token in map(self._normalize_phrase, text.split()) if token]

    def _request_lines(self) -> list:
        """The token lists of the weekday_for_date lines; a slot is one token."""
        cache_key = f"{self.lang}:weekday_for_date.lines"
        if cache_key not in self.resources.static:
            lines = []
            resource = ResourceFile(self.resources.types.intent, "weekday_for_date")
            if resource.file_path:
                with open(resource.file_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            lines.extend(self._tokens(re.sub(r"\{[^}]*\}", " {} ", sentence))
                                         for sentence in expand(line))
            self.resources.static[cache_key] = lines
        return self.resources.static[cache_key]

    def _request_words(self) -> set:
        """The words of the lines that hold no slot, without the weekday names."""
        cache_key = f"{self.lang}:weekday_for_date.words"
        if cache_key not in self.resources.static:
            words = {token for line in self._request_lines() if "{}" not in line
                     for token in line}
            for name in self._load_cached_entity("weekday"):
                words.difference_update(self._tokens(name.replace("-", " ")))
            self.resources.static[cache_key] = words
        return self.resources.static[cache_key]

    def _request_triples(self) -> set:
        """The runs of three neighbouring words in the lines, a slot excluded."""
        cache_key = f"{self.lang}:weekday_for_date.triples"
        if cache_key not in self.resources.static:
            self.resources.static[cache_key] = {
                triple for line in self._request_lines()
                for triple in zip(line, line[1:] + ["$"], line[2:] + ["$", "$"]) if "{}" not in triple}
        return self.resources.static[cache_key]

    def _is_dateless_slot(self, slot: str) -> bool:
        """Check whether a slot that does not parse holds only request words.

        An engine may bind the tail of a slot-free line to the date slot
        ("what weekday is it please" binds "it please"). Such a slot names no
        date. "blorp" and "it in tokyo" hold words the slot-free lines lack.
        """
        slot_words = self._tokens(slot)
        return bool(slot_words) and set(slot_words) <= self._request_words()

    def _get_requested_date(self, message, now, ignore=None):
        """Return the date a weekday request is about, or None.

        A bound ``date`` slot is the date; a slot that does not parse is no
        date, unless it holds only words of the slot-free request lines. A
        request that binds no slot is read whole, and one that holds no date
        is about today, unless it holds a number the parser cannot read. ``ignore``
        holds the (start, end) spans of the weekdays the utterance names; the
        engine may capture them inside the slot, so the whole utterance, with
        those weekdays blanked, is read instead.
        """
        raw = message.data.get("utterance", "")
        utterance = self._blank_weekday_questions(raw)
        slot = message.data.get("date") or ""
        if slot.casefold() in raw.casefold() and slot.casefold() not in utterance.casefold():
            slot = ""  # the engine bound a phrase that asks for the weekday
        slot = self._blank_weekday_questions(slot).strip()
        if slot and all(self.voc_match(word, "date_article") for word in slot.split()):
            slot = ""  # the engine bound a bare article, which the parser reads as the number 1
        if ignore:
            text = utterance.casefold()
            for start, end in sorted(ignore, reverse=True):
                text = f"{text[:start]} {text[end:]}"
            return self._parse_date(text, now)
        dt = self._parse_date(slot or utterance, now)
        if dt:
            return dt
        if slot:
            return now if self._is_dateless_slot(slot) else None
        # a digit the parser could not read is a date it failed on, not a request for today
        return None if re.search(r"\d", utterance) else now

    def _get_named_holiday(self, utterance: str, now) -> Optional[datetime.datetime]:
        """Return the next date of the holiday the utterance names, or None."""
        found = extract_holiday_date(utterance, self.lang, ref_date=now.date())
        return datetime.datetime.combine(found[0], now.timetz()) if found else None

    def _render_weekday(self, weekday_index: int) -> str:
        """Render a localized weekday from a weekday index."""
        reference_monday = datetime.datetime(2024, 1, 1)
        return nice_weekday(reference_monday + datetime.timedelta(days=weekday_index),
                            lang=self.lang)

    def _get_leap_year_query_scope(self, utterance: str) -> str:
        """Return whether the user asked about the current, next, or either year."""
        if self.voc_match(utterance, "leap_year_scope_either", lang=self.lang):
            return "either"
        if self.voc_match(utterance, "leap_year_scope_next", lang=self.lang):
            return "next"
        return "current"

    @staticmethod
    def _get_timezone_from_builtins(location_string: str) -> Optional[datetime.tzinfo]:
        """Attempt to resolve a timezone from a location name using geocoding.

        Args:
            location_string (str): The location name or timezone string.

        Returns:
            Optional[datetime.tzinfo]: The corresponding timezone, or None if not found.
        """
        if "/" not in location_string:
            try:
                # This handles common city names, like "Dallas" or "Paris"
                # first get the lat / long.
                g = geocoder.osm(location_string)

                # now look it up
                tf = TimezoneFinder()
                timezone = tf.timezone_at(lng=g.lng, lat=g.lat)
                return pytz.timezone(timezone)
            except Exception:
                pass

        try:
            # This handles codes like "America/Los_Angeles"
            return pytz.timezone(location_string)
        except Exception:
            pass
        return None

    def _get_timezone_from_table(self, location_string: str) -> Optional[datetime.tzinfo]:
        """Resolve timezone using a manually defined lookup table.

        Args:
            location_string (str): The location string to resolve.

        Returns:
            Optional[datetime.tzinfo]: The corresponding timezone, or None if not found.
        """
        timezones = self.resources.load_named_value_file("timezone.value", ',')
        for timezone in timezones:
            if location_string.lower() == timezone.lower():
                try:
                    return pytz.timezone(timezones[timezone].strip())
                except pytz.UnknownTimeZoneError:
                    LOG.error(f"timezone.value maps {timezone!r} to "
                              f"{timezones[timezone].strip()!r}, which pytz does not know")
                    return None
        return None

    def _get_timezone_from_fuzzymatch(self, location_string: str) -> Optional[datetime.tzinfo]:
        """Fuzzymatch a location against the pytz timezones.

        The pytz timezones consists of
        Location/Name pairs.  For example:
            ["Africa/Abidjan", "Africa/Accra", ... "America/Denver", ...
             "America/New_York", ..., "America/North_Dakota/Center", ...
             "Cuba", ..., "EST", ..., "Egypt", ..., "Etc/GMT+3", ...
             "Etc/Zulu", ... "US/Eastern", ... "UTC", ..., "Zulu"]

        These are parsed and compared against the provided location.
        """
        target = location_string.lower()
        best = None
        for name in pytz.all_timezones:
            # Separate at '/'
            normalized = name.lower().replace("_", " ").split("/")
            if len(normalized) == 1:
                pct = fuzzy_match(normalized[0], target)
            elif len(normalized) >= 2:
                # Check for locations like "Sydney"
                pct1 = fuzzy_match(normalized[1], target)
                # locations like "Sydney Australia" or "Center North Dakota"
                pct2 = fuzzy_match(normalized[-2] + " " + normalized[-1],
                                   target)
                pct3 = fuzzy_match(normalized[-1] + " " + normalized[-2],
                                   target)
                pct = max(pct1, pct2, pct3)
            if not best or pct >= best[0]:
                best = (pct, name)
        if best and best[0] > 0.8:
            # solid choice
            return pytz.timezone(best[1])
        elif best and best[0] > 0.3:
            say = speakable_timezone(best[1])
            if self.ask_yesno("did_you_mean_timezone",
                              data={"zone_name": say}) == "yes":
                return pytz.timezone(best[1])
        else:
            return None

    def get_timezone_in_location(self, location_string: str) -> datetime.tzinfo:
        """Get the timezone for a given location using multiple fallback strategies.

        This method attempts to resolve a timezone by checking built-in resources,
        a custom lookup table, and finally fuzzy matching.

        Args:
            location_string (str): A string representing a location (e.g., city or region).

        Returns:
            datetime.tzinfo: The timezone object if resolved, else None.
        """
        if self._is_ambiguous_location(location_string):
            return None
        timezone = self._get_timezone_from_builtins(location_string)
        if not timezone:
            timezone = self._get_timezone_from_table(location_string)
        if not timezone:
            timezone = self._get_timezone_from_fuzzymatch(location_string)
        return timezone

    ######################################################################
    # utils
    def get_datetime(self, location: str = None,
                     anchor_date: datetime.datetime = None) -> Optional[datetime.datetime]:
        """Return the localized datetime for a given location or current session.

        Args:
            location (str, optional): A location name for timezone conversion.
            anchor_date (datetime.datetime, optional): A reference date. Defaults to now.

        Returns:
            Optional[datetime.datetime]: The localized datetime, or None if timezone cannot be resolved.
        """
        if location:
            tz = self.get_timezone_in_location(location)
            if not tz:
                return None  # tz not found
        else:
            # self.location_timezone comes from Session
            tz = pytz.timezone(self.location_timezone)
        if anchor_date:
            dt = anchor_date.astimezone(tz)
        else:
            dt = now_local(tz)
        return dt

    def get_spoken_time(self, location: str = None,
                        anchor_date: datetime.datetime = None) -> Optional[str]:
        """Get a human-readable spoken version of the current time.

        Args:
            location (str, optional): Location for timezone conversion.
            anchor_date (datetime.datetime, optional): Specific time to use instead of now.

        Returns:
            str: A spoken-friendly representation of the time.
        """
        dt = self.get_datetime(location, anchor_date)
        if not dt:
            return None

        s = nice_time(dt, lang=self.lang, speech=True,
                      use_24hour=self.use_24hour, use_ampm=not self.use_24hour)
        # HACK: Mimic 2 has a bug with saying "AM".  Work around it for now.
        if not self.use_24hour:
            s = s.replace("AM", "A.M.")
        return s

    def get_display_time(self, location: str = None,
                         anchor_date: datetime.datetime = None) -> Optional[str]:
        """Get a display-friendly version of the current time.

        Args:
            location (str, optional): Location for timezone conversion.
            anchor_date (datetime.datetime, optional): Specific time to use instead of now.

        Returns:
            str: A string representing the display time.
        """
        dt = self.get_datetime(location, anchor_date)
        if not dt:
            return None
        return nice_time(dt, lang=self.lang,
                         speech=False,
                         use_24hour=self.use_24hour,  # session aware
                         use_ampm=not self.use_24hour)

    def get_display_date(self, location: str = None,
                         anchor_date: datetime.datetime = None) -> str:
        """Get a localized and display-friendly version of the current date.

        Args:
            location (str, optional): Location name for timezone context.
            anchor_date (datetime.datetime, optional): Date to display instead of now.

        Returns:
            str: A string representing the formatted date.
        """
        dt = self.get_datetime(location, anchor_date)
        fmt = self.date_format  # Session aware
        if fmt == 'MDY':
            return dt.strftime("%-m/%-d/%Y")
        elif fmt == 'YMD':
            return dt.strftime("%-Y/%-m/%d")
        elif fmt == 'YDM':
            return dt.strftime("%-Y/%-d/%m")
        elif fmt == 'DMY':
            return dt.strftime("%d/%-m/%-Y")

    ######################################################################
    # Time queries / display
    def speak_time(self, dialog: str, location: str = None,
                   anchor_date: datetime.datetime = None):
        """Speak the current time. Optionally at a location
        speaks an error if timezone for requested location could not be detected"""
        if location:
            current_time = self.get_spoken_time(location, anchor_date=anchor_date)
            if not current_time:
                self.speak_dialog("time_tz_not_found", {"location": location})
                return
            time_string = self.get_display_time(location, anchor_date=anchor_date)
        else:
            current_time = self.get_spoken_time(anchor_date=anchor_date)
            time_string = self.get_display_time(anchor_date=anchor_date)

        # speak it
        self.speak_dialog(dialog, {"time": current_time})

        # and briefly show the time
        if time_string:
            self.show_time(time_string)

    @intent_handler("what_time_is_it.intent")
    def handle_query_time(self, message):
        """Handle queries about the current time."""
        location = self._resolve_location(message.data.get("location"))
        # speak it
        self.speak_time("time_current", location=location)

    @intent_handler("what_time_will_it_be.intent")
    def handle_query_future_time(self, message):
        normalizer = UtteranceNormalizerPlugin.get_normalizer(self.lang)
        utt = normalizer.normalize(message.data["utterance"])

        # {number:offset} (OVOS-INTENT-1 5.6): the typed-slot map carries the
        # number, and a pipeline MAY ignore the hint entirely, so `None` says
        # nothing about why (no map, no parser for the language, nothing
        # said). The words are the one source every engine leaves intact:
        # parse them first, and ask only when they hold no offset. Asking on
        # `None` alone turned a working answer into a question on any engine
        # that computes no map.
        dt, utt = extract_datetime(utt, lang=self.lang) or (None, None)
        if not dt and self.typed_slot(message, "offset") is None:
            response = self.get_response("ask_offset")
            if not response:
                return
            dt, utt = extract_datetime(normalizer.normalize(response),
                                       lang=self.lang) or (None, None)

        if not dt:
            self.handle_query_time(message)
            return

        location = self._resolve_location(message.data.get("location"))

        # speak it
        self.speak_time("time_future", location=location, anchor_date=dt)

    ######################################################################
    # Date queries
    def handle_query_date(self, message, response_type="simple"):
        """Handle queries about the current date."""
        utt = message.data.get('utterance', "").lower()
        now = self.get_datetime()  # session aware
        try:
            dt, utt = extract_datetime(utt, anchorDate=now, lang=self.lang) or (now, utt)
        except Exception:
            self.log.exception(f"failed to extract date from '{utt}'")
            dt = now

        # handle questions ~ "what is the day in sydney"
        location_string = self._resolve_location(message.data.get("location"))

        if location_string:
            dt = self.get_datetime(location_string, anchor_date=dt)
            if not dt:
                self.speak_dialog("time_tz_not_found",
                                  {"location": location_string})
                return  # failed in timezone lookup

        speak_date = nice_date(dt, lang=self.lang)
        # speak it
        if response_type == "simple":
            self.speak_dialog("date", {"date": speak_date})
        elif response_type == "relative":
            # remove time data to get clean dates
            day_date = dt.replace(hour=0, minute=0,
                                  second=0, microsecond=0)
            today_date = now.replace(hour=0, minute=0,
                                     second=0, microsecond=0)
            num_days = (day_date - today_date).days
            if num_days >= 0:
                speak_num_days = nice_duration(num_days * 86400, lang=self.lang)
                self.speak_dialog("date_relative_future",
                                  {"date": speak_date,
                                   "num_days": speak_num_days})
            else:
                # if in the past, make positive before getting duration
                speak_num_days = nice_duration(num_days * -86400, lang=self.lang)
                self.speak_dialog("date_relative_past",
                                  {"date": speak_date,
                                   "num_days": speak_num_days})

        # and briefly show the date
        self.show_date(dt, location=location_string)

    @intent_handler("time_until.intent")
    def handle_time_until(self, message):
        """Answer how far away one date is, or how many days lie between two.

        A request that names two dates fills the {start} and {end} slots and
        gets the day count between them. A request that names one date gets
        that date and its distance from today.
        """
        if "start" in message.data or "end" in message.data:
            self._speak_days_between(message)
        else:
            self.handle_query_date(message, response_type="relative")

    @intent_handler("what_day_is_it.intent")
    def handle_current_day(self, message):
        """Speak today's date with its weekday, optionally at a {location}.

        The answer is always today: a request such as "was ist heute für ein
        Tag" names no other date, so the utterance is not parsed for one. A
        language that ``nice_date`` cannot format gets the day through the
        day_current dialog.
        """
        location = self._resolve_location(message.data.get("location"))
        now = self.get_datetime(location)
        if location and not now:
            self.speak_dialog("time_tz_not_found", {"location": location})
            return
        try:
            spoken = nice_date(now, lang=self.lang)
        except (KeyError, NotImplementedError):  # ovos-date-parser has no date format for the language
            self.speak_dialog("day_current", {"day": nice_day(now, lang=self.lang)})
        else:
            self.speak_dialog("date", {"date": spoken})
        self.show_date(now, location=location)

    @intent_handler("weekday_for_date.intent")
    def handle_weekday(self, message):
        """Speak the weekday of a date, or answer a yes/no weekday question.

        A request that names no date is about today. A yes/no question that
        names a weekday gets the yes/no dialogs, and so does a request that
        names a weekday and another day: a holiday, or a date with digits that
        the text without the weekday reads as a day other than today, unless
        the whole text reads as the weekday. Digits that the parser cannot
        read in a yes/no question give the date error. A holiday the utterance names is the date, and the weekday it names is
        the answer to check, not the date.
        """
        now = self.get_datetime()  # session aware
        utterance = message.data.get("utterance", "")
        named = self._find_named_weekdays(utterance)
        # several weekdays joined by "or" ask which one it is
        choice = len({index for index, _ in named}) > 1 and self.voc_match(
            utterance, "weekday_or", lang=self.lang)
        holiday = self._get_named_holiday(utterance, now)
        has_digits = bool(re.search(r"\d", utterance))
        read = None
        other = alone = None  # the date it names besides its weekday; the weekday read alone
        if named and not choice:
            index, span = named[-1]
            other = holiday or self._get_requested_date(message, now, ignore=[span])
            if holiday or self._is_yes_no_question(utterance):
                if other is None and has_digits:
                    self.speak_dialog("extract_date_error")
                    return
                self._speak_weekday_match(other or now, now, index)
                return
            alone = self._parse_date(utterance[slice(*span)], now)
            # digits that move the whole text's date off the weekday's own are a date;
            # a time or a year beside the weekday leave it there
            if has_digits and other and other.date() != now.date():
                whole = self._parse_date(self._blank_weekday_questions(utterance), now)
                # a time beside the weekday is no date, whatever "last" or "next" moves
                is_time = other.time() != datetime.time()
                if not (is_time or (alone and whole and whole.date() == alone.date())):
                    self._speak_weekday_match(other, now, index)
                    return
                read = whole

        dt = holiday or read or self._get_requested_date(
            message, now, ignore=[span for _, span in named] if choice else None)
        if choice and dt is None and not has_digits:
            dt = now
        if has_digits and other is None and alone and dt and dt.date() == alone.date():
            dt = None  # the digits are a date the parser could not read
        if dt is None:
            self.speak_dialog("extract_date_error")
            return
        if dt.date() == now.date():
            self.speak_dialog("weekday_current",
                              {"weekday": nice_weekday(now, lang=self.lang)})
            return
        dialog = ("weekday_at_date_future" if dt.date() > now.date()
                  else "weekday_at_date_past")
        self.speak_dialog(dialog, {
            "date": nice_date(dt, lang=self.lang, now=now),
            "weekday": nice_weekday(dt, lang=self.lang)})

    def _speak_weekday_match(self, dt, now, expected_weekday: int):
        """Answer whether a date falls on the weekday the user named."""
        data = {
            "date": nice_date(dt, lang=self.lang, now=now),
            "weekday": self._render_weekday(expected_weekday),
            "actual_weekday": nice_weekday(dt, lang=self.lang)
        }
        matches = dt.weekday() == expected_weekday
        if dt.date() > now.date():
            dialog = ("weekday_matches_date_future_yes" if matches
                      else "weekday_matches_date_future_no")
        elif dt.date() == now.date():
            dialog = ("weekday_matches_date_today_yes" if matches
                      else "weekday_matches_date_today_no")
        else:
            dialog = ("weekday_matches_date_past_yes" if matches
                      else "weekday_matches_date_past_no")
        self.speak_dialog(dialog, data)

    def _speak_days_between(self, message):
        """Count the calendar days between two dates named in the utterance.

        The date extractor returns one date per text, so each date has its own
        slot ({start}, {end}) and is extracted on its own. Both are anchored
        at "now", and the answer is the absolute number of days, so the order
        the dates are spoken in does not matter.
        """
        now = self.get_datetime()  # session aware
        dates = []
        for slot in ("start", "end"):
            text = message.data.get(slot)
            dt = None
            if text:
                try:
                    dt, _ = extract_datetime(text, anchorDate=now,
                                             lang=self.lang) or (None, None)
                except Exception:
                    self.log.exception(f"failed to extract date from '{text}'")
            if not dt:
                self.speak_dialog("extract_date_error")
                return
            dates.append(dt)

        start, end = sorted(dates)
        num_days = abs((end.date() - start.date()).days)
        if num_days == 0:
            self.speak_dialog("days_between_same", {
                "date": nice_date(start, lang=self.lang, now=now)})
            return
        self.speak_dialog("days_between", {
            "num_days": nice_duration(num_days * 86400, lang=self.lang).strip(),
            "from_date": nice_date(start, lang=self.lang, now=now),
            "to_date": nice_date(end, lang=self.lang, now=now)})

    @intent_handler("what_month_is_it.intent")
    def handle_current_month(self, message):
        """
        Handles queries about the current month and speaks its name.
        
        Args:
            message: The message object containing the user's request.
        """
        now = self.get_datetime()  # session aware
        self.speak_dialog("month_current",
                          {"month": nice_month(now, lang=self.lang)})

    @intent_handler("what_year_is_it.intent")
    def handle_current_year(self, message):
        now = self.get_datetime()  # session aware
        self.speak_dialog("year_current",
                          {"year": nice_year(now, lang=self.lang)})

    @intent_handler("date_future_weekend.intent")
    def handle_date_future_weekend(self, message):
        """
        Handles queries about the upcoming weekend's dates.
        
        Determines the dates for the next Saturday and Sunday, formats them for speech, and responds with a dialog containing both dates.
        """
        now = self.get_datetime()
        utt = message.data.get("utterance", "").lower()
        weekday = now.weekday()

        # On Saturday/Sunday, default to the upcoming weekend unless the user
        # explicitly asked for the current weekend in this locale.
        if weekday <= 5:
            saturday_dt = now + datetime.timedelta(days=5 - weekday)
        else:
            saturday_dt = now - datetime.timedelta(days=1)

        if weekday >= 5 and not self._mentions_current_weekend(utt):
            saturday_dt += datetime.timedelta(days=7)

        sunday_dt = saturday_dt + datetime.timedelta(days=1)
        saturday_date = ', '.join(nice_date(saturday_dt, lang=self.lang).split(', ')[:2])
        sunday_date = ', '.join(nice_date(sunday_dt, lang=self.lang).split(', ')[:2])
        self.speak_dialog('date_future_weekend', {
            'saturday_date': saturday_date,
            'sunday_date': sunday_date
        })

    # TODO - merge date_last_weekend.intent and date_future_weekend.intent handlers
    #  use voc_match or something to disambiguate
    @intent_handler("date_last_weekend.intent")
    def handle_date_last_weekend(self, message):
        # Strip year off nice_date as request is inherently close
        # Don't pass `now` to `nice_date` as a
        # request on Monday will return "yesterday"
        """
        Handles the intent to provide the dates of the previous weekend.
        
        Speaks a dialog with the formatted dates for last Saturday and Sunday.
        """
        now = self.get_datetime()
        dt = extract_datetime('last saturday',
                              anchorDate=now, lang='en-us')[0]
        saturday_date = ', '.join(nice_date(dt, lang=self.lang).split(', ')[:2])
        dt = extract_datetime('last sunday',
                              anchorDate=now, lang='en-us')[0]
        sunday_date = ', '.join(nice_date(dt, lang=self.lang).split(', ')[:2])
        self.speak_dialog('date_last_weekend', {
            'saturday_date': saturday_date,
            'sunday_date': sunday_date
        })

    @intent_handler("next_leap_year.intent")
    def handle_query_next_leap_year(self, message):
        """
        Handles the intent to provide the year of the next leap year.
        
        Determines the next leap year based on the current date and speaks the result to the user.
        """
        now = self.get_datetime()
        leap_date = now_local().replace(month=2, day=28)
        year = now.year if now <= leap_date else now.year + 1
        next_leap_year = get_next_leap_year(year)
        self.speak_dialog('next_leap_year', {'year': next_leap_year})

    @intent_handler("is_leap_year.intent")
    def handle_is_leap_year(self, message):
        """Handle yes/no questions about leap years."""
        utterance = message.data.get("utterance", "")
        now = self.get_datetime()
        current_year = now.year
        next_year = current_year + 1
        scope = self._get_leap_year_query_scope(utterance)

        if scope == "either":
            if calendar.isleap(current_year):
                self.speak_dialog("leap_year_either_yes",
                                  {"year": current_year})
            elif calendar.isleap(next_year):
                self.speak_dialog("leap_year_either_yes",
                                  {"year": next_year})
            else:
                self.speak_dialog("leap_year_either_no",
                                  {"year": get_next_leap_year(next_year)})
            return

        if scope == "next":
            if calendar.isleap(next_year):
                self.speak_dialog("leap_year_next_yes", {"year": next_year})
            else:
                self.speak_dialog("leap_year_next_no",
                                  {"year": next_year})
            return

        if calendar.isleap(current_year):
            self.speak_dialog("leap_year_current_yes",
                              {"year": current_year})
        else:
            self.speak_dialog("leap_year_current_no",
                              {"year": current_year})

    ######################################################################
    # GUI / Faceplate
    def show_date(self, dt: datetime.datetime, location: str):
        """Display date on GUI and Mark 1 faceplate."""
        self.show_date_gui(dt, location)
        self.show_date_mark1(dt)

    def show_date_mark1(self, dt: datetime.datetime):
        show = self.get_display_date(anchor_date=dt)
        LOG.debug(f"sending date to mk1 {show}")
        self.bus.emit(Message("ovos.mk1.display_date",
                              {"text": show}))

    def show_date_gui(self, dt: datetime.datetime, location: str):
        self.gui.clear()
        self.gui['location_string'] = str(location)
        self.gui['date_string'] = self.get_display_date(anchor_date=dt)
        self.gui['weekday_string'] = nice_weekday(dt, lang=self.lang)
        self.gui['day_string'] = dt.strftime('%d')
        self.gui['month_string'] = nice_month(dt, lang=self.lang)
        self.gui['year_string'] = dt.strftime("%Y")
        if self.date_format == 'MDY':
            self.gui['daymonth_string'] = f"{self.gui['month_string']} {self.gui['day_string']}"
        else:
            self.gui['daymonth_string'] = f"{self.gui['day_string']} {self.gui['month_string']}"
        self.gui.show_page('date')

    def show_time(self, display_time: str):
        """Display time on GUI and Mark 1 faceplate."""
        self.show_time_gui(display_time)
        self.show_time_mark1(display_time)

    def show_time_mark1(self, display_time: str):
        LOG.debug(f"Emitting ovos.mk1.display_time with time: {display_time}")
        self.bus.emit(Message("ovos.mk1.display_time", {"text": display_time}))

    def show_time_gui(self, display_time):
        """ Display time on the GUI. """
        self.gui.clear()
        self.gui['time_string'] = display_time
        self.gui['ampm_string'] = ''
        self.gui['date_string'] = self.get_display_date()
        self.gui.show_page('time')
