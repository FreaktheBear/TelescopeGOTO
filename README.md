Introduction
This readme describes the (attempts) to convert a table top Dobsonian telescope to a Newtonian telescope including guidance via Stellarium.
Equatorial mounts have a preference for most astronomers as it compensates for the (tilted) earth rotation axis so that tracking and astro photography are possible.
Of course you can buy an equatorial mount which will give you all the possibilities for serious stargazing.
For me it is an interesting project which involves both theoretical and practical parts which makes it fun for me to learn new stuff.

Initiation of the project
As I received a donated broken Dobsonian which I was able to repair, I quickly understood that finding and "tracking" objects via this table top Dobsonian is not very easy.
Looking at the moon is okay but other object quickly pose a challenge.
I looked at a step by step approach on how I could improve the capabilities of the telescope.
I did my research on the web and there are numerous DIY projects of people who are attempting and/or succeeding in this endeavour.
After trying out different software I decided to start first with a "push to" solution based on a Raspberry Pi Pico interfacing with a Raspberry Pi 4B which runs Stellarium.
The intent of the Pi Pico is to measure Right Ascension and Declination which is send to the RPI4B over serial UART using the telescope control plugin of Stellarium.
If that would work then I would try to fully automate the Dobsonian mount to a GOTO mount with steppermotors.
