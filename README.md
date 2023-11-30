# wp4-sol-gel-reaction-stage

This script is designed to control an orbital shaker mixing stage (specifically Electrothermal RS9000 Agitation Reaction Station) for sol-gel processing.
It is intended to work through an external microcontroller board (Arduino Uno with Ethernet Shield) connected to the instrument with RS232 (Digilent Pmod RS232 Module).
The microcontroller is accessed over LAN using the 'requests' python library.
The microcontroller currently uses a custom sketch contained in this repo.
Plans are in place to replace this with a generic sketch for wider applicability.
In its present form, the script will only work as intended if a microcontroller (IP address defined in the script) is connected to the network.

The script allows for temperature and speed setpoints to be pre-programmed, with the reaction stage then running autonomously and shutting down once expected time has elapsed.
In present form, the script allows for one temperature and two sequential speed setpoints (for fast and slow ramp steps).
The default process steps are contained in the file: Orbit_Shaker_Default_Ramp.csv, which can be read into the process setup and modified.

The current script needs only to be run by a python interpreter on a workstation PC sharing a LAN connection with a suitable microcontroller.
