# Feathergate
A lightweight Frigate viewer based on PyGame, designed to run on embedded systems.

To run, first edit the config.yaml to your needs, then do `python3 feathergate.py`

SystemD Unit:
```
[Unit]
Description=Feathergate - Frigate MJPEG Grid Display
After=network.target graphical.target

[Service]
WorkingDirectory=/opt/feathergate/
ExecStart=/usr/bin/python3 /opt/feathergate/feathergate.py
Restart=always
RestartSec=5s
StandardOutput=journal
StandardError=journal
Environment=DISPLAY=:0

[Install]
WantedBy=graphical.target
```
