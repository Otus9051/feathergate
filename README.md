# Feathergate
A lightweight Frigate viewer based on PyGame, designed to run on embedded systems.

To run, first edit the config.yaml to your needs, then do `python3 feathergate.py`, to exit, press "x"

Caveats: 
- Please run it as the user that is currently logged in to the graphical console, and preferably via the graphical console, else it will have issues.
- On Raspberry Pis, there may be high CPU usage due to a fault in the loop logic: https://raspberrypi.stackexchange.com/questions/8077/how-can-i-lower-the-usage-of-cpu-for-this-python-program ; A fix is on the way.
