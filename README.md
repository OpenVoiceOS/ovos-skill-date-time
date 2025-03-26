# <img src='https://raw.githack.com/FortAwesome/Font-Awesome/master/svgs/solid/calendar.svg' card_color='#22a7f0' width='50' height='50' style='vertical-align:bottom'/> Date and Time
Get the time, date, day of the week

## About 
Get the local time or time for major cities around the world.  Times are given in 12-hour (2:30 pm) or 24-hour format (14:30) based on the Time Format setting in your `mycroft.conf`

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

You can adjust certain aspects of this skill's behavior by configuring the `settings.json` file. 

2 sound files are included with the skill, `"casio-watch.wav"` and `"clock-chime.mp3"`, to audibly signal when the hour changes

Below is an example configuration file with explanations for each option.

```json
{
    "play_hour_chime": true,
    "hour_sound": "clock-chime.mp3"
}
```

- **`play_hour_chime`**: (boolean) Enables or disables the hourly chime notification. If `true`, the skill will play an audio chime at the start of every hour. Default is `false`.
- **`hour_sound`**: (string) Specifies the file path to the audio file used for the hourly chime. By default, it points to `casio-watch.wav` in the `res` folder. You can customize this with the path to any audio file you prefer.

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
