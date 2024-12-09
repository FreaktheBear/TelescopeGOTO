# Introduction
This readme describes the (attempts) to convert a table top Dobsonian telescope to a Newtonian GOTO telescope including tracking control via Stellarium.
Equatorial mounts have a preference for most astronomers as it compensates for the (tilted) earth rotation axis (perpendicular to the equatorial plane) so that tracking and astro photography are possible.

As I received a donated broken Dobsonian, which I was able to repair, I quickly understood that finding and "tracking" objects via this table top Dobsonian is not very easy. Looking at the moon is okay but other objects quickly pose a challenge. I looked at a step by step approach on how I could improve the capabilities of the telescope.

I did my research on the web and there are numerous DIY projects of people who are attempting and/or succeeding in this endeavour.
After trying out different things I decided to start first with a "push to" solution based on a Raspberry Pi Pico interfacing with a Raspberry Pi 4B which runs Stellarium. The intent of the Pi Pico is to measure Right Ascension and Declination which is send to the RPI 4B over serial UART using the telescope control plugin of Stellarium. If that would work then I would try to fully automate the Dobsonian mount to a GOTO Newtonian mount with stepper motors.

Of course you can buy an equatorial mount which will give you all the bells and whistles for serious stargazing.
For me it is an interesting project which involves both theoretical and practical parts which makes it fun for me to learn new stuff.

## Objectives
1. Having a challenging project to learn MicroPython on a Raspberry Pi Pico for the telescope control, and communication with Stellarium on a Raspberry Pi 4b.
2. Low cost, with most "mechanical" parts from a local DIY shop.
3. Allignment and positioning based upon data from a 9-axis MPU and a GPS module. (Update: one MPU poses too much problems getting the correct right ascension / declination data for the NextStar protocol, so I decided to use two MPU6050's for the moment)
4. Tracking based on NEMA 17 stepper motors driven by A4988 drivers and pulsed from the Pi Pico PIO.

## Issues log
(moved github issues log)

| Issue No.| Description | Date reported | Date resolved | Solution |
| -------- | -------- | -------- | -------- | -------- |
| 001 | Stellarium RPI does not communicate with GPS | 2024-10 | 2024-10 | Stellarium Github discusion #3936. Libgps-dev was not included into the RPI Stellarium source. Stellarium Team added libgs-dev to source |
| 002 | Tried to build Stellarium from source for RPI Bookworm, but ran into issues | 2024-10 | 2024-10 | Stellarium Github discussion #3943. Deb and deb-src of Jammy Main can be used as a repository to install Stellarium onto RPI Bookworm |
| 003 | LX200 serial command set uses "special" characters which I was not able to use within VSCode vREPL (double ?? are printed) | 2024-10 | 2024-10 | Using NexStar serial communication protocol instead
| 004 | Pico UART PINs 16 and 17 caused jitter with driving the A4988 stepper driver | 2024-10-31 | 2024-11-03 | Changed to pins 10 and 11 to drive the motor and fast steps were possible |
|  |  |  |  |  |

## Some pictures

Herewith a few pictures of the design so far.
Currently the right ascension and declination stepper motors will move the mount to an initial position (_Pico_ reticle 0 hours / 0 degrees) based on the feedback of two MPU6050 Accellero/Gyro sensors

![mount1](images/mount1.jpg)

![mount2](images/mount2.jpg)

![stellarium1](images/stellarium.png)





