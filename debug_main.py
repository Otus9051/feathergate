#!/usr/bin/env python3
"""
Minimal version of main.py with debug output to track the actual flow
"""
import os
os.environ['PYGAME_BLEND_ALPHA_SDL2'] = '1'

import requests
import threading
import time
import pygame
import sys
import yaml
from PIL import Image

# Import the necessary modules and globals
from config_manager import load_config
from frigate_manager import get_frigate_token, fetch_and_process_image, current_images, camera_last_updated, image_lock, camera_intervals, camera_motion_states, is_mqtt_configured
from mqtt_manager import mqtt_thread_loop

def main():
    """Minimal main function with debug output."""
    global is_mqtt_configured
    try:
        print("DEBUG: Starting application...")
        
        # Load configuration
        config = load_config()
        print("DEBUG: Config loaded")
        
        # Initialize Pygame (minimal)
        pygame.init()
        pygame.display.set_mode((100, 100))  # Tiny window for testing
        print("DEBUG: Pygame initialized")

        session = requests.Session()
        if not get_frigate_token(config, session):
            print("DEBUG: Failed to get initial token. Exiting.")
            return

        print("DEBUG: Frigate token obtained")
        
        # Initialize global state and placeholders
        camera_names = config['frigate']['camera_names']
        target_image_size = (320, 240)  # Small for testing

        # Check if the MQTT configuration exists and is enabled
        mqtt_config = config.get('mqtt')
        if mqtt_config and mqtt_config.get('enabled', False) and all(key in mqtt_config for key in ['broker_host', 'broker_port']):
            is_mqtt_configured = True
            print("DEBUG: MQTT is configured, starting MQTT thread...")
            # Start MQTT thread
            mqtt_t = threading.Thread(target=mqtt_thread_loop, args=(config,), daemon=True)
            mqtt_t.start()
            print("DEBUG: MQTT thread started")
        else:
            is_mqtt_configured = False
            print("DEBUG: MQTT is disabled")
        
        # Initialize initial camera update intervals and placeholders based on MQTT status
        default_interval = config['display']['interval_rate_min']
        if not is_mqtt_configured:
            default_interval = config['display']['interval_rate_max']
            
        with image_lock:
            for name in camera_names:
                placeholder_surface = pygame.Surface(target_image_size)
                placeholder_surface.fill((0, 0, 0))
                current_images[name] = placeholder_surface
                camera_last_updated[name] = 0
                camera_intervals[name] = default_interval
                camera_motion_states[name] = False
                print(f"📋 MINIMAL DEBUG: Initialized {name} - interval={default_interval}, motion=False")
        
        # Start only ONE image fetching thread for testing
        test_camera = camera_names[0]
        print(f"DEBUG: Starting image fetching for {test_camera}")
        thread = threading.Thread(target=fetch_and_process_image, args=(config, session, test_camera, target_image_size), daemon=True)
        thread.start()

        # Monitor states for 60 seconds
        print("DEBUG: Monitoring for 60 seconds...")
        start_time = time.time()
        
        while time.time() - start_time < 60:
            # Check states every 3 seconds
            with image_lock:
                states = {name: camera_motion_states.get(name, 'unknown') for name in camera_names}
                intervals = {name: camera_intervals.get(name, 'unknown') for name in camera_names}
            
            print(f"📊 MINIMAL DEBUG [{time.strftime('%H:%M:%S')}]:")
            for name in camera_names:
                print(f"  {name}: motion={states[name]}, interval={intervals[name]}")
            
            time.sleep(3)
        
        print("DEBUG: Test completed")

    except KeyboardInterrupt:
        print("\nDEBUG: Interrupted by user")
    except Exception as e:
        print(f"DEBUG: Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pygame.quit()

if __name__ == "__main__":
    main()
