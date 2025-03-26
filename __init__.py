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
import datetime
import os
import re
from typing import Optional

import geocoder
import pytz
from ovos_bus_client.message import Message
from ovos_date_parser import nice_time, extract_datetime, nice_date, nice_duration, date_time_format, nice_weekday, \
    nice_month, nice_day, nice_year
from ovos_utils import classproperty
from ovos_utils.log import LOG
from ovos_utils.parse import fuzzy_match
from ovos_utils.process_utils import RuntimeRequirements
from ovos_utils.time import now_local, get_next_leap_year
from ovos_utterance_normalizer import UtteranceNormalizerPlugin
from ovos_workshop.decorators import intent_handler
from ovos_workshop.intents import IntentBuilder
from ovos_workshop.skills import OVOSSkill
from timezonefinder import TimezoneFinder


def speakable_timezone(tz):
    """Convert timezone to a better speakable version

    Splits joined words, e.g. EasterIsland to "Easter Island",
    "North_Dakota" to "North Dakota" etc.
    Then parses the output into the correct order for speech,
    e.g. "America/North Dakota/Center" to
    resulting in something like "Center North Dakota America", or
    "Easter Island Chile"
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
        """Check if the time format is in 24-hour mode.
        self.time_format is Session aware"""
        return self.time_format == 'full'

    ######################################################################
    # parsing
    def _extract_location(self, utt: str) -> str:
        """Extract location from utterance."""
        rx_file = self.find_resource('location.rx', 'regex')
        if rx_file:
            with open(rx_file) as f:
                for pat in f.read().splitlines():
                    pat = pat.strip()
                    if pat and pat[0] == "#":
                        continue
                    res = re.search(pat, utt)
                    if res:
                        try:
                            return res.group("Location")
                        except IndexError:
                            pass
        return None

    @staticmethod
    def _get_timezone_from_builtins(location_string: str) -> Optional[datetime.tzinfo]:
        """Get timezone from built-in resources."""
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
        """Check lookup table for timezones.

        This can also be a translation layer.
        E.g. "china = GMT+8"
        """
        timezones = self.resources.load_named_value_file("timezone.value", ',')
        for timezone in timezones:
            if location_string.lower() == timezone.lower():
                # assumes translation is correct
                return pytz.timezone(timezones[timezone].strip())
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
            if self.ask_yesno("did.you.mean.timezone",
                              data={"zone_name": say}) == "yes":
                return pytz.timezone(best[1])
        else:
            return None

    def get_timezone_in_location(self, location_string: str) -> datetime.tzinfo:
        """Get the timezone.

        This uses a variety of approaches to determine the intended timezone.
        If locale is the user defined locale, we save that timezone and cache it.
        """
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
        """return anchor_date/now_local at location/session_tz"""
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

    def get_spoken_time(self, location: str = None, force_ampm=False,
                        anchor_date: datetime.datetime = None) -> str:
        """Get formatted spoken time based on user preferences."""
        dt = self.get_datetime(location, anchor_date)

        # speak AM/PM when talking about somewhere else
        say_am_pm = bool(location) or force_ampm

        s = nice_time(dt, lang=self.lang, speech=True,
                      use_24hour=self.use_24hour, use_ampm=say_am_pm)
        # HACK: Mimic 2 has a bug with saying "AM".  Work around it for now.
        if say_am_pm:
            s = s.replace("AM", "A.M.")
        return s

    def get_display_time(self, location: str = None, force_ampm=False,
                         anchor_date: datetime.datetime = None) -> str:
        """Get formatted display time based on user preferences."""
        dt = self.get_datetime(location, anchor_date)
        # speak AM/PM when talking about somewhere else
        say_am_pm = bool(location) or force_ampm
        return nice_time(dt, lang=self.lang,
                         speech=False,
                         use_24hour=self.use_24hour,  # session aware
                         use_ampm=say_am_pm)

    def get_display_date(self, location: str = None,
                         anchor_date: datetime.datetime = None) -> str:
        """Get formatted display date based on user preferences."""
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
    def speak_time(self, dialog: str, location: str = None):
        """Speak the current time. Optionally at a location
        speaks an error if timezone for requested location could not be detected"""
        if location:
            current_time = self.get_spoken_time(location)
            if not current_time:
                self.speak_dialog("time.tz.not.found", {"location": location})
                return
            time_string = self.get_display_time(location)
        else:
            current_time = self.get_spoken_time()
            time_string = self.get_display_time()

        # speak it
        self.speak_dialog(dialog, {"time": current_time})

        # and briefly show the time
        self.show_time(time_string)

    @intent_handler(IntentBuilder("").require("Query").require("Time").
                    optionally("Location"))
    def handle_query_time(self, message):
        """Handle queries about the current time."""
        utt = message.data.get('utterance', "")
        location = message.data.get("Location") or self._extract_location(utt)
        # speak it
        self.speak_time("time.current", location=location)

    @intent_handler("what.time.is.it.intent")
    def handle_current_time_simple(self, message):
        self.handle_query_time(message)

    @intent_handler("what.day.is.it.intent")
    def handle_current_day_simple(self, message):
        now = self.get_datetime()  # session aware
        self.speak_dialog("day.current",
                          {"day": nice_day(now, lang=self.lang)})


    @intent_handler("what.weekday.is.it.intent")
    def handle_current_weekday_simple(self, message):
        now = self.get_datetime()  # session aware
        self.speak_dialog("weekday.current",
                          {"weekday": nice_weekday(now, lang=self.lang)})

    @intent_handler("what.month.is.it.intent")
    def handle_current_month_simple(self, message):
        now = self.get_datetime()  # session aware
        self.speak_dialog("month.current",
                          {"month": nice_month(now, lang=self.lang)})

    @intent_handler("what.year.is.it.intent")
    def handle_current_year_simple(self, message):
        now = self.get_datetime()  # session aware
        self.speak_dialog("year.current",
                          {"year": nice_year(now, lang=self.lang)})

    @intent_handler("what.time.will.it.be.intent")
    def handle_query_future_time(self, message):
        normalizer = UtteranceNormalizerPlugin.get_normalizer(self.lang)
        utt = normalizer.normalize(message.data["utterance"])

        dt, utt = extract_datetime(utt, lang=self.lang) or (None, None)
        if not dt:
            self.handle_query_time(message)
            return

        location = message.data.get("Location") or self._extract_location(utt)
        # speak it
        self.speak_time("time.future", location=location)

    @intent_handler(IntentBuilder("").optionally("Query").
                    require("Time").require("Future").optionally("Location"))
    def handle_future_time_simple(self, message):
        self.handle_query_future_time(message)

    @intent_handler(IntentBuilder("").require("Display").require("Time").
                    optionally("Location"))
    def handle_show_time(self, message):
        utt = message.data.get('utterance', "")
        location = message.data.get("Location") or self._extract_location(utt)
        time_string = self.get_display_time(location)
        # show time
        self.show_time(time_string)
        # TODO - implement "clock homescreen" in mk1 plugin,
        #   emit bus message to enable it

    ######################################################################
    # Date queries
    def handle_query_date(self, message, response_type="simple"):
        """Handle queries about the current date."""
        utt = message.data.get('utterance', "").lower()
        now = self.get_datetime()  # session aware
        try:
            dt, utt = extract_datetime(utt, anchorDate=now, lang=self.lang) or (now, utt)
        except Exception as e:
            self.log.exception(f"failed to extract date from '{utt}'")
            dt = now

        # handle questions ~ "what is the day in sydney"
        location_string = message.data.get("Location") or self._extract_location(utt)

        if location_string:
            dt = self.get_datetime(location_string, anchor_date=dt)
            if not dt:
                self.speak_dialog("time.tz.not.found",
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
                self.speak_dialog("date.relative.future",
                                  {"date": speak_date,
                                   "num_days": speak_num_days})
            else:
                # if in the past, make positive before getting duration
                speak_num_days = nice_duration(num_days * -86400, lang=self.lang)
                self.speak_dialog("date.relative.past",
                                  {"date": speak_date,
                                   "num_days": speak_num_days})

        # and briefly show the date
        self.show_date(dt, location=location_string)

    @intent_handler(IntentBuilder("").require("Query").require("Date").
                    optionally("Location"))
    def handle_query_date_simple(self, message):
        """Handle simple date queries."""
        self.handle_query_date(message, response_type="simple")

    @intent_handler(IntentBuilder("").require("Query").require("Month"))
    def handle_day_for_date(self, message):
        self.handle_query_date(message, response_type="relative")

    @intent_handler(IntentBuilder("").require("Query").require("RelativeDay")
                    .optionally("Date"))
    def handle_query_relative_date(self, message):
        if self.voc_match(message.data.get('utterance', ""), 'Today'):
            self.handle_query_date(message, response_type="simple")
        else:
            self.handle_query_date(message, response_type="relative")

    @intent_handler(IntentBuilder("").require("RelativeDay").require("Date"))
    def handle_query_relative_date_alt(self, message):
        if self.voc_match(message.data.get('utterance', ""), 'Today'):
            self.handle_query_date(message, response_type="simple")
        else:
            self.handle_query_date(message, response_type="relative")

    @intent_handler("date.future.weekend.intent")
    def handle_date_future_weekend(self, message):
        # Strip year off nice_date as request is inherently close
        # Don't pass `now` to `nice_date` as a
        # request on Friday will return "tomorrow"
        now = self.get_datetime()
        dt = extract_datetime('this saturday', anchorDate=now, lang='en-us')[0]
        saturday_date = ', '.join(nice_date(dt, lang=self.lang).split(', ')[:2])
        dt = extract_datetime('this sunday', anchorDate=now, lang='en-us')[0]
        sunday_date = ', '.join(nice_date(dt, lang=self.lang).split(', ')[:2])
        self.speak_dialog('date.future.weekend', {
            'saturday_date': saturday_date,
            'sunday_date': sunday_date
        })

    @intent_handler("date.last.weekend.intent")
    def handle_date_last_weekend(self, message):
        # Strip year off nice_date as request is inherently close
        # Don't pass `now` to `nice_date` as a
        # request on Monday will return "yesterday"
        now = self.get_datetime()
        dt = extract_datetime('last saturday',
                              anchorDate=now, lang='en-us')[0]
        saturday_date = ', '.join(nice_date(dt, lang=self.lang).split(', ')[:2])
        dt = extract_datetime('last sunday',
                              anchorDate=now, lang='en-us')[0]
        sunday_date = ', '.join(nice_date(dt, lang=self.lang).split(', ')[:2])
        self.speak_dialog('date.last.weekend', {
            'saturday_date': saturday_date,
            'sunday_date': sunday_date
        })

    @intent_handler(IntentBuilder("").require("Query").require("LeapYear"))
    def handle_query_next_leap_year(self, message):
        now = self.get_datetime()
        leap_date = datetime.datetime(now.year, 2, 28)
        year = now.year if now <= leap_date else now.year + 1
        next_leap_year = get_next_leap_year(year)
        self.speak_dialog('next.leap.year', {'year': next_leap_year})

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
