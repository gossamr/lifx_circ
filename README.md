# lifx_circ
Circadian-tuned LIFX control daemon

This tool is meant to provide simple circadian LUT behavior for your LIFX lights. Controls LIFX via [lightsd](https://github.com/lopter/lightsd).

I've included a sample LUT ('lut.json') intended to mimic the color temperature of sunlight, but any application or LUT of any length is acceptable.

Lat/Long settings in that LUT are used to allow Pyephem to extract and localize timing of events named 'sunrise', 'noon', and 'sunset' on a daily basis.

If you enable the 'extended-sunlight-mode' flag, those events will be localized based on their timings during the day of the Summer solstice. - I leave that feature on as I enjoy the 'SAD'-fighting effects of extended blue light during the short Winter days, but if you want to strictly mimic the sun's behavior, turn it off.

Run script is lifx_bg.py ...
That hosts a bootstrap HTTP controller avail at localhost:7777 with a power toggle for now ... will be adding a bypass to that sometime soon so you can override the LUT behavior and manually control settings.

This is still WIP but I'm hacking on it.

