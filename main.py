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
from display_manager import setup_display, display_splash_screen, main_display_loop

def main():
    """Main function to run the application."""
    global is_mqtt_configured
    try:
        # Load configuration
        config = load_config()
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(f"Configuration error: {e}")
        return

    # Initialize Pygame and display
    screen, font = setup_display(config)

    # Display initial splash screens
    display_splash_screen(screen, font, "FeatherGate by Otus9051", config)
    time.sleep(2)
    display_splash_screen(screen, font, "Authenticating with Frigate...", config)

    session = requests.Session()
    if not get_frigate_token(config, session):
        print("Failed to get initial token. Exiting.")
        pygame.quit()
        sys.exit()

    # After getting the token, determine motion detection mode
    display_splash_screen(screen, font, "Configuring motion detection...", config)
    from motion_api_manager import sync_initial_motion_state, start_api_polling_mode
    
    display_splash_screen(screen, font, "Initializing threads...", config)
    
    # Initialize global state and placeholders
    camera_names = config['frigate']['camera_names']
    grid_rows = config['display']['grid_rows']
    grid_cols = config['display']['grid_cols']
    display_resolution = tuple(config['display']['resolution'])

    single_image_width = display_resolution[0] // grid_cols
    single_image_height = display_resolution[1] // grid_rows
    target_image_size = (single_image_width, single_image_height)

    # Configure motion detection mode
    mqtt_config = config.get('mqtt', {})
    api_only_mode = mqtt_config.get('api_only_mode', False)
    mqtt_enabled = mqtt_config.get('enabled', False)
    mqtt_available = mqtt_enabled and all(key in mqtt_config for key in ['broker_host', 'broker_port'])
    
    if api_only_mode:
        # User specifically wants API-only mode
        is_mqtt_configured = False
        print("API-only mode enabled")
        start_api_polling_mode(config, session)
        
    elif mqtt_available:
        # Hybrid mode: MQTT for real-time + API for initial state
        is_mqtt_configured = True
        print("Hybrid mode - MQTT + API")
        
        # Start MQTT thread for real-time updates
        mqtt_t = threading.Thread(target=mqtt_thread_loop, args=(config,), daemon=True)
        mqtt_t.start()
        
        # Get initial state from API
        sync_initial_motion_state(config, session)
        
    else:
        # No MQTT available, fall back to API-only
        is_mqtt_configured = False
        print("MQTT not available - using API fallback")
        start_api_polling_mode(config, session)
    
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
    
    # Start image fetching threads
    for camera_name in camera_names:
        thread = threading.Thread(target=fetch_and_process_image, args=(config, session, camera_name, target_image_size), daemon=True)
        thread.start()

    # Wait for all cameras to have their first image
    display_splash_screen(screen, font, "Waiting for initial images...", config)
    all_cameras_loaded = False
    while not all_cameras_loaded:
        with image_lock:
            all_cameras_loaded = all(camera_last_updated[cam] > 0 for cam in camera_names)
        time.sleep(0.1)

    # Calculate grid positions
    grid_positions = []
    for row in range(grid_rows):
        for col in range(grid_cols):
            x = col * single_image_width
            y = row * single_image_height
            grid_positions.append((x, y))

    # Run the main display loop, now with the `is_mqtt_configured` status
    main_display_loop(config, screen, font, grid_positions, target_image_size, is_mqtt_configured)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"An unhandled error occurred: {e}")
    finally:
        pygame.quit()
        print("Exiting application.")
        sys.exit()
