# The timezone source
<!-- agent-hint
covers: where the skill gets the timezone for a request with and without a location
source: __init__.py (get_datetime, get_timezone_in_location, _get_timezone_from_builtins, _get_timezone_from_table, _get_timezone_from_fuzzymatch)
generated: no
verify: (p=$(grep -o '^[0-9]\. `_[a-z_]*`' docs/timezone.md | cut -d'`' -f2 | tr '\n' ' '); c=$(sed -n '/def get_timezone_in_location/,/return timezone/p' __init__.py | grep -o 'self\._[a-z_]*(' | tr -d '(' | sed 's/self\.//' | tr '\n' ' '); [ "$p" = "$c" ] || { echo "order: page [$p], code [$c]"; exit 1; }; for v in 0.8 0.3; do grep -q "best\[0\] > $v" __init__.py && grep -q "$v" docs/timezone.md || { echo "threshold $v"; exit 1; }; done; echo OK)
see: settings.md
-->

A request with no location uses the timezone of the session. A request that names a place ("what time is it in Paris") uses the timezone of that place.

## No location

`get_datetime` uses `self.location_timezone`, the timezone of the session location. The clock is `now_local` in that timezone.

## A named location

The `{location}` slot of the intent holds the place. The skill removes the phrases in `non_location_phrases.intent` of the locale, so a phrase such as "right now" is not a place. `get_timezone_in_location` then tries these steps in order and stops at the first result:

1. `_is_ambiguous_location`: a place in `ambiguous_locations.intent` (for example "australia", "usa") has more than one timezone. The skill gives no timezone.
2. `_get_timezone_from_builtins`: a name without "/" goes to the OpenStreetMap geocoder (`geocoder.osm`), and `timezonefinder` gets the zone at those coordinates. This step needs the network. A name such as `America/Los_Angeles` goes to `pytz.timezone`.
3. `_get_timezone_from_table`: the `timezone_<zone>.voc` files of the locale map place names to a zone. For example, `timezone_us_eastern.voc` maps "east coast" to `US/Eastern`.
4. `_get_timezone_from_fuzzymatch`: the skill compares the place with the names of all pytz zones. A score above 0.8 selects the zone. A score above 0.3 makes the skill ask `did_you_mean_timezone` and use the zone on a yes.

When no step gives a timezone, the skill speaks `time_tz_not_found` with the place name.

The timezone boundary data comes from timezonefinder-data, under the Open Database License (see the README credits).

---
[← Prev](settings.md) · [Home](index.md) · [Next →](testing.md)
