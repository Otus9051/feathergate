import requests
import io
import time
import threading
from PIL import Image
import pygame

# Global state dictionaries for inter-thread communication
# These must be managed with a lock.
current_images = {}
camera_last_updated = {}
camera_intervals = {}
camera_motion_states = {}
image_lock = threading.Lock()
api_token = None
token_refresh_time = 0
# This is a placeholder; its value is set dynamically by main.py after reading the config.
is_mqtt_configured = False

# Wake-up events for each camera to interrupt sleep when motion state changes
camera_wake_events = {}

def wake_camera_thread(camera_name):
    """
    Wake up a specific camera's image fetching thread immediately.
    Used when motion state changes to avoid delays.
    """
    if camera_name in camera_wake_events:
        camera_wake_events[camera_name].set()

def get_frigate_token(config, session):
    """
    Fetches an auth token from the Frigate API.

    Args:
        config (dict): The application configuration.
        session (requests.Session): The session object to use for the request.

    Returns:
        bool: True if the token was successfully fetched, False otherwise.
    """
    global api_token, token_refresh_time
    
    frigate_base_url = config['frigate']['base_url']
    username = config['frigate']['username']
    password = config['frigate']['password']
    
    login_url = f"{frigate_base_url}/api/login"
    payload = {"user": username, "password": password}
    headers = {"Content-Type": "application/json"}

    try:
        response = session.post(login_url, json=payload, headers=headers, verify=False, timeout=10)
        response.raise_for_status()

        frigate_cookie = response.cookies.get('frigate_token')
        if frigate_cookie:
            with image_lock:
                api_token = frigate_cookie
                token_refresh_time = time.time()
            return True
        else:
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Error getting Frigate API token: {e}")
        if response and response.status_code == 401:
            print("Login credentials likely incorrect for /api/login.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred in get_frigate_token: {e}")
        return False

def fetch_and_process_image(config, session, camera_name, target_image_size):
    """
    Continuously fetches the latest image for a camera and updates the display surface.

    Args:
        config (dict): The application configuration.
        session (requests.Session): The session object for the request.
        camera_name (str): The name of the camera to fetch.
        target_image_size (tuple): The desired size for the image surface.
    """
    global api_token, image_lock, camera_wake_events
    last_fetch_time = time.time()
    
    # Create wake-up event for this camera
    if camera_name not in camera_wake_events:
        camera_wake_events[camera_name] = threading.Event()
    
    frigate_base_url = config['frigate']['base_url']
    image_resampling_method = getattr(Image.Resampling, config.get('advanced', {}).get('image_resampling', 'BICUBIC').upper(), Image.Resampling.BICUBIC)
    token_lifetime_seconds = config.get('advanced', {}).get('token_lifetime_seconds', 3600)

    while True:
        try:
            # Re-obtain token if expired or not yet set
            with image_lock:
                if not api_token or (time.time() - token_refresh_time > token_lifetime_seconds):
                    get_frigate_token(config, session)
                headers = {"Authorization": f"Bearer {api_token}"}
                current_interval = camera_intervals.get(camera_name, config['display']['interval_rate_min'])

            # Calculate how long to wait, but allow wake-up events to interrupt
            time_to_wait = current_interval - (time.time() - last_fetch_time)
            if time_to_wait > 0:
                # Use event.wait() with timeout instead of time.sleep()
                # This allows the thread to be woken up immediately when motion state changes
                camera_wake_events[camera_name].wait(timeout=time_to_wait)
                # Clear the event for next time
                camera_wake_events[camera_name].clear()
            
            last_fetch_time = time.time() 

            image_url = f"{frigate_base_url}/api/{camera_name}/latest.jpg"
            response = session.get(image_url, headers=headers, stream=True, verify=False, timeout=10)
            response.raise_for_status() 

            image_data = io.BytesIO(response.content)
            pil_image = Image.open(image_data).convert("RGB")
            pil_image = pil_image.resize(target_image_size, image_resampling_method)
            pygame_image = pygame.image.fromstring(pil_image.tobytes(), pil_image.size, pil_image.mode)

            with image_lock:
                current_images[camera_name] = pygame_image
                camera_last_updated[camera_name] = time.time()

        except requests.exceptions.RequestException as e:
            print(f"Error fetching image for {camera_name}: {e}")
            time.sleep(5) 
        except Exception as e:
            print(f"CRITICAL ERROR in {camera_name} fetching loop: {e}")
            time.sleep(5)
