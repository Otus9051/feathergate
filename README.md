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

## Application Workflow:
### 1. Initialization:
  - main.py invokes config_manager.py to read the config.
  - PyGame and Display started by main.py, splash screen shown.
  - Session token acquired by frigate_manager.py.
  - Camera grid initialized.
  - MQTT Configuration checked and verified.
  - `interval_rate_min` and `interval_rate_max` set from config.
### 2. Display:
  - frigate_manager.py starts fetching latest JPGs for each camera based on interval rates, motion, and MQTT status.
  - display_manager.py scales JPGs with Pillow and shows them accordingly in the grid along with other display options like timestamps.
  - Loop runs indefinitely until exit.
