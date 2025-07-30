import requests
import pygame
from PIL import Image
import io
import time
import threading
import json
import yaml

CONFIG_FILE = "config.yaml"

try:
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    print(f"Error: {CONFIG_FILE} not found. Please create it.")
    exit(1)
except yaml.YAMLError as e:
    print(f"Error parsing {CONFIG_FILE}: {e}")
    exit(1)

FRIGATE_BASE_URL = config['frigate']['base_url']
FRIGATE_USERNAME = config['frigate']['username']
FRIGATE_PASSWORD = config['frigate']['password']
CAMERA_NAMES = config['frigate']['camera_names']

DISPLAY_RESOLUTION = tuple(config['display']['resolution'])
GRID_ROWS = config['display']['grid_rows']
GRID_COLS = config['display']['grid_cols']
INTERVAL_SECONDS = config['display']['interval_seconds']
FONT_SIZE = config['display']['font_size']

TOKEN_LIFETIME_SECONDS = config.get('advanced', {}).get('token_lifetime_seconds', 3600 * 24 * 365 * 50)
IMAGE_RESAMPLING_METHOD = getattr(Image.Resampling, config.get('advanced', {}).get('image_resampling', 'BICUBIC').upper(), Image.Resampling.BICUBIC)
CHUNK_SIZE = config.get('advanced', {}).get('chunk_size', 8192)

FPS_TARGET = 1 / INTERVAL_SECONDS
SINGLE_IMAGE_WIDTH = DISPLAY_RESOLUTION[0] // GRID_COLS
SINGLE_IMAGE_HEIGHT = DISPLAY_RESOLUTION[1] // GRID_ROWS
TARGET_IMAGE_SIZE = (SINGLE_IMAGE_WIDTH, SINGLE_IMAGE_HEIGHT)

pygame.init()
screen = pygame.display.set_mode(DISPLAY_RESOLUTION, pygame.FULLSCREEN | pygame.NOFRAME)
pygame.mouse.set_visible(False)

current_images = {}
image_lock = threading.Lock()
api_token = None
token_refresh_time = 0

for name in CAMERA_NAMES:
    placeholder_surface = pygame.Surface(TARGET_IMAGE_SIZE)
    placeholder_surface.fill((0, 0, 0))
    current_images[name] = placeholder_surface

font = pygame.font.Font(None, FONT_SIZE)

def get_frigate_token(session):
    global api_token, token_refresh_time
    
    login_url = f"{FRIGATE_BASE_URL}/api/login"
    payload = {
        "username": FRIGATE_USERNAME,
        "password": FRIGATE_PASSWORD
    }
    headers = {"Content-Type": "application/json"}

    print("Attempting to get Frigate API token (from cookie)...")
    try:
        response = session.post(login_url, json=payload, headers=headers, verify=False, timeout=10)
        
        print(f"Login API Status Code: {response.status_code}")
        
        response.raise_for_status()

        frigate_cookie = response.cookies.get('frigate_token')
        if frigate_cookie:
            api_token = frigate_cookie
            token_refresh_time = time.time()
            print("Successfully obtained Frigate API token from Set-Cookie header.")
            return True
        else:
            print(f"Login successful (200 OK), but 'frigate_token' cookie not found in response.")
            print(f"Available cookies: {response.cookies.keys()}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Error getting Frigate API token: {e}")
        if response and response.status_code == 401:
            print("Login credentials likely incorrect for /api/login.")
        elif response and response.status_code == 200:
            print("Got 200 OK, but likely a malformed response not containing the cookie.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred in get_frigate_token: {e}")
        return False

def fetch_and_process_image_mjpeg(session, camera_name):
    global api_token

    while True:
        if api_token is None or (time.time() - token_refresh_time > TOKEN_LIFETIME_SECONDS):
            print(f"[{camera_name}] Token is missing or expired, attempting to refresh.")
            if not get_frigate_token(session):
                print(f"[{camera_name}] Failed to get/refresh token. Cannot fetch MJPEG stream.")
                time.sleep(5)
                continue

        headers = {"Authorization": f"Bearer {api_token}"}
        mjpeg_url = f"{FRIGATE_BASE_URL}/api/{camera_name}/mjpeg" 

        boundary = b"" 
        try:
            response = session.get(mjpeg_url, stream=True, headers=headers, verify=False, timeout=None)
            response.raise_for_status() 

            if response.status_code == 401:
                print(f"[{camera_name}] MJPEG stream returned 401. Token likely invalid. Forcing refresh.")
                api_token = None
                response.close()
                time.sleep(1)
                continue

            content_type = response.headers.get('Content-Type', '')
            if 'boundary=' in content_type:
                boundary_raw = content_type.split('boundary=')[1].strip()
                if boundary_raw.startswith('"') and boundary_raw.endswith('"'):
                    boundary_raw = boundary_raw[1:-1]
                boundary = (b'--' + boundary_raw.encode('utf-8'))
                print(f"[{camera_name}] Detected MJPEG boundary: {boundary.decode()}")
            else:
                print(f"[{camera_name}] Warning: No MJPEG boundary found. Using common fallback.")
                boundary = b'--frigate_boundary' 

            if not boundary:
                print(f"[{camera_name}] Critical: Could not determine MJPEG boundary. Retrying stream in 5s...")
                time.sleep(5)
                continue

            bytes_read = b''
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                bytes_read += chunk
                
                a = bytes_read.find(boundary)
                if a != -1:
                    b = bytes_read.find(boundary, a + len(boundary))
                    if b != -1:
                        header_and_image_data = bytes_read[a + len(boundary):b]
                        jpeg_start = header_and_image_data.find(b'\xff\xd8')
                        if jpeg_start != -1:
                            image_data = header_and_image_data[jpeg_start:]
                            
                            try:
                                img = Image.open(io.BytesIO(image_data))
                                img = img.convert("RGB")
                                img = img.resize(TARGET_IMAGE_SIZE, IMAGE_RESAMPLING_METHOD)
                                
                                pygame_surface = pygame.image.fromstring(img.tobytes(), img.size, img.mode)
                                
                                with image_lock:
                                    current_images[camera_name] = pygame_surface
                                
                            except Exception as img_e:
                                print(f"[{camera_name}] Error processing image data: {img_e}. Frame skipped.")
                        
                        bytes_read = bytes_read[b:]
                    
        except requests.exceptions.RequestException as e:
            print(f"[{camera_name}] Stream error: {e}. Reconnecting in 5s...")
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
                print(f"[{camera_name}] Stream 401. Token might be invalid. Forcing refresh.")
                api_token = None
            time.sleep(5)
        except Exception as e:
            print(f"[{camera_name}] Unexpected error in MJPEG stream: {e}. Reconnecting in 5s...")
            time.sleep(5)

def fetching_thread_loop(session):
    threads = []
    for camera_name in CAMERA_NAMES:
        thread = threading.Thread(target=fetch_and_process_image_mjpeg, args=(session, camera_name))
        threads.append(thread)
        thread.daemon = True
        thread.start()
    
    while True:
        time.sleep(1)

def main_display_loop():
    running = True
    session = requests.Session()

    if not get_frigate_token(session):
        print("Failed to get initial token. Exiting.")
        pygame.quit()
        return

    fetch_thread = threading.Thread(target=fetching_thread_loop, args=(session,), daemon=True)
    fetch_thread.start()

    grid_positions = []
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            x = col * SINGLE_IMAGE_WIDTH
            y = row * SINGLE_IMAGE_HEIGHT
            grid_positions.append((x, y))

    clock = pygame.time.Clock()

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.K_ESCAPE:
                running = False

        screen.fill((0, 0, 0))

        with image_lock:
            for i, camera_name in enumerate(CAMERA_NAMES):
                img_surface = current_images[camera_name]
                screen.blit(img_surface, grid_positions[i])

                if img_surface.get_at((0,0)) == (0,0,0) and img_surface.get_size() == TARGET_IMAGE_SIZE:
                     text_surface = font.render(f"Loading {camera_name}...", True, (255, 255, 255))
                     text_rect = text_surface.get_rect(center=(grid_positions[i][0] + SINGLE_IMAGE_WIDTH // 2, 
                                                                grid_positions[i][1] + SINGLE_IMAGE_HEIGHT // 2))
                     screen.blit(text_surface, text_rect)

        pygame.display.flip()
        clock.tick(FPS_TARGET) 

if __name__ == "__main__":
    try:
        main_display_loop()
    except Exception as e:
        print(f"A truly unhinged error occurred: {e}")
    finally:
        pygame.quit()
        print("Exiting application.")
        exit(0)
