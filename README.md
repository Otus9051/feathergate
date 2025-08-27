<header>
    <br>
    <div align="center">
        <img width="30%" alt="feathergate" src="https://github.com/user-attachments/assets/00a5ad62-8e42-4df4-aa4c-7063fdf2fc4d" />
    </div>
    <h2 align="center">FeatherGate</h2>
    <h3 align="center">A lightweight Frigate viewer for low-spec devices</h3>
    <p align="center">
        No-nonsense, native, and fast, with Dynamic Refresh abilities
    </p>
</header>

---

### Features:
- PyGame for low graphical usage
- Highly configurable, add as many cameras, tweak image processing, etc.
- Dynamic Refresh for each camera based on MQTT
- Designed to run on low-spec hardware

## Getting Started:
### Prerequisites:
- Python >3.8
- Frigate NVR
- MQTT Broker (for Dynamic Refresh, optional)
- Required libraries in `requirements.txt`

### Installation:
```
git clone https://github.com/Otus9051/feathergate
cd feathergate
pip install -r requirements.txt
```
Please edit the `config.yaml` with your data before starting the application.
### Usage:
```
python3 main.py
```
To exit, press `x`

## Check Wiki for documentation
Or you can also go to https://deepwiki.com/Otus9051/feathergate/1-overview because I don't have time

## Credits:
- PyGame and SDL for Display
- Frigate NVR APIs
- EMQX MQTT Broker
- itsbhanusharma for testing
