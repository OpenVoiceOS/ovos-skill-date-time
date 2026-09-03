# <img src='https://raw.githack.com/FortAwesome/Font-Awesome/master/svgs/solid/calendar.svg' card_color='#22a7f0' width='50' height='50' style='vertical-align:bottom'/> Date and Time

Get the time, date, and day of the week.

## About

This skill gets the local time or the time in major cities around the world. It gives times in 12-hour format (2:30 pm) or 24-hour format (14:30), based on the Time Format setting in your `mycroft.conf`.

## Examples

* "What time is it?"
* "What time is it in Paris?"
* "Show me the time"
* "What day is it"
* "What's the date?"
* "Tell me the day of the week"
* "How many days until July 4th"
* "What day is Memorial Day 2020?"

## Configuration

You can adjust the skill's behavior in the `settings.json` file.

The skill includes 2 sound files, `"casio-watch.wav"` and `"clock-chime.mp3"`, to signal when the hour changes.

Below is an example configuration file with explanations for each option.

```json
{
    "play_hour_chime": true,
    "hour_sound": "clock-chime.mp3"
}
```

- **`play_hour_chime`**: (boolean) Turns the hourly chime on or off. If `true`, the skill plays an audio chime at the start of every hour. The default is `false`.
- **`hour_sound`**: (string) Sets the path to the audio file for the hourly chime. By default, it points to `casio-watch.wav` in the `res` folder. You can set it to the path of any audio file you prefer.

## Related projects

- [OpenVoiceOS/ovos-date-parser](https://github.com/OpenVoiceOS/ovos-date-parser): parses and formats dates and times for this skill.
- [OpenVoiceOS/ovos-workshop](https://github.com/OpenVoiceOS/ovos-workshop): the skill framework this skill builds on.
- [OpenVoiceOS/ovos-utterance-normalizer](https://github.com/OpenVoiceOS/ovos-utterance-normalizer): normalizes utterances before intent matching.

## Credits

- [casio-watch.wav by @Pablobd](https://freesound.org/people/Pablobd/sounds/492481/) under the [CC0 1.0 Universal License](https://creativecommons.org/publicdomain/zero/1.0/)
- [clock-chime.mp3 by @ecfike](https://pixabay.com/sound-effects/clock-chime-88027/) under the [Pixabay Content License](https://pixabay.com/service/license-summary/)
- Original skill by Mycroft AI (@MycroftAI)

## Category
**Daily**

## Tags
#date
#time
#clock
#world-time
#world-clock
#date-time
