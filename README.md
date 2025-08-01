# Feathergate
A lightweight Frigate viewer based on PyGame, designed to run on embedded systems.

To run, first edit the config.yaml to your needs, then do `python3 feathergate.py`, to exit, press "x"
Enable MQTT to get Dynamic Refresh which refreshes only the camera that has motion at a faster rate, being economic.

Caveats: 
- Please run it as the user that is currently logged in to the graphical console, and preferably via the graphical console, else it will have issues.