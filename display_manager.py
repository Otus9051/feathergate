import pygame
import datetime
import os
import time
from frigate_manager import image_lock, current_images, camera_last_updated, camera_motion_states

def setup_display(config):
    """Initializes Pygame and sets up the screen."""
    try:
        pygame.init()
        
        # Set display flags for better performance
        display_flags = pygame.FULLSCREEN | pygame.NOFRAME
        if hasattr(pygame, 'DOUBLEBUF'):
            display_flags |= pygame.DOUBLEBUF
        if hasattr(pygame, 'HWSURFACE'):
            display_flags |= pygame.HWSURFACE
        
        display_resolution = tuple(config['display']['resolution'])
        screen = pygame.display.set_mode(display_resolution, display_flags)
        pygame.mouse.set_visible(False)
        
        # Disable event types we don't need to reduce event queue overhead
        pygame.event.set_blocked([
            pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP, pygame.MOUSEBUTTONDOWN,
            pygame.JOYAXISMOTION, pygame.JOYBALLMOTION, pygame.JOYHATMOTION,
            pygame.JOYBUTTONUP, pygame.JOYBUTTONDOWN, pygame.ACTIVEEVENT,
            pygame.VIDEORESIZE, pygame.VIDEOEXPOSE
        ])
        
        font_size = config['display']['font_size']
        font = pygame.font.Font(None, font_size)
        
        return screen, font
    except pygame.error as e:
        print(f"Failed to initialize Pygame display: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error in display setup: {e}")
        raise

def display_splash_screen(screen, font, message, config):
    """
    Displays a splash screen with a given message and logo.
    
    Args:
        screen (pygame.Surface): The screen surface to draw on.
        font (pygame.font.Font): The font object to use for text.
        message (str): The message to display.
        config (dict): The application configuration.
    """
    try:
        screen.fill((0, 0, 0)) # Black background for splash
        
        splash_image_path = config['display'].get('splash_image_path')
        # Construct an absolute path to the image to ensure it is found.
        # This assumes the image is in the same directory as the main script.
        if splash_image_path:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            full_path = os.path.join(script_dir, splash_image_path)
            if os.path.exists(full_path):
                try:
                    logo_image = pygame.image.load(full_path).convert_alpha()
                    logo_rect = logo_image.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2 - 100))
                    screen.blit(logo_image, logo_rect)
                except pygame.error as e:
                    print(f"Error loading splash image from '{full_path}': {e}. No image displayed.")
            else:
                print(f"Splash image not found at '{full_path}'. No image displayed.")
        
        splash_font = pygame.font.Font(None, font.get_height() * 2) # Larger font for emphasis
        text_surface = splash_font.render(message, True, (255, 255, 255)) # White text
        text_rect = text_surface.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2 + 100))
        screen.blit(text_surface, text_rect)
        pygame.display.flip() # Make sure it's drawn to the screen
    except Exception as e:
        print(f"Error displaying splash screen: {e}")
        # Fallback: just clear screen and show text
        try:
            screen.fill((0, 0, 0))
            text_surface = font.render(message, True, (255, 255, 255))
            text_rect = text_surface.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2))
            screen.blit(text_surface, text_rect)
            pygame.display.flip()
        except Exception:
            pass  # Silently fail if even basic text rendering fails

def main_display_loop(config, screen, font, grid_positions, target_image_size, is_mqtt_configured):
    """
    The main Pygame display loop. Renders the camera feeds and overlays.

    Args:
        config (dict): The application configuration.
        screen (pygame.Surface): The Pygame screen surface.
        font (pygame.font.Font): The Pygame font object.
        grid_positions (list): A list of (x, y) coordinates for each camera feed.
        target_image_size (tuple): The size of each camera feed surface.
        is_mqtt_configured (bool): The status of the MQTT connection.
    """
    running = True
    camera_names = config['frigate']['camera_names']
    show_timestamps = config['display']['show_timestamps']
    single_image_width = target_image_size[0]
    
    # The frame rate is controlled per-camera by the frigate_manager intervals
    # No need for global FPS limiting since each camera fetches at its own rate
    
    # Cache for text surfaces to avoid re-rendering identical text
    text_cache = {}
    
    # Track last states to minimize unnecessary updates
    last_motion_states = {}
    last_timestamps = {}
    last_image_versions = {}
    
    # Initialize state tracking
    for camera_name in camera_names:
        last_motion_states[camera_name] = None
        last_timestamps[camera_name] = None
        last_image_versions[camera_name] = None
    
    # Create static text surfaces that don't change often
    mqtt_off_suffix = " (MQTT OFF)"
    
    def get_cached_text(text, color, force_refresh=False):
        """Get a cached text surface or create a new one."""
        cache_key = (text, color)
        if force_refresh or cache_key not in text_cache:
            text_cache[cache_key] = font.render(text, True, color)
        return text_cache[cache_key]
    
    def get_timestamp_string(timestamp):
        """Convert timestamp to formatted string, with caching."""
        if timestamp <= 0:
            return None
        # Round to seconds to reduce cache misses
        rounded_ts = int(timestamp)
        if rounded_ts not in text_cache:
            dt = datetime.datetime.fromtimestamp(rounded_ts)
            text_cache[rounded_ts] = dt.strftime("%H:%M:%S")
        return text_cache[rounded_ts]

    while running:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_x:
                running = False

        # Copy current state once to minimize lock time
        with image_lock:
            current_state = {
                'images': dict(current_images),
                'last_updated': dict(camera_last_updated),
                'motion_states': dict(camera_motion_states)
            }
        
        # DEBUG: Print motion states every few seconds
        current_time = time.time()
        if not hasattr(main_display_loop, 'last_debug_time'):
            main_display_loop.last_debug_time = 0
        
        if current_time - main_display_loop.last_debug_time > 5:  # Every 5 seconds
            print(f"🔍 DISPLAY DEBUG - Current motion states:")
            for cam_name in camera_names:
                motion_state = current_state['motion_states'].get(cam_name, 'unknown')
                print(f"  {cam_name}: motion={motion_state}")
            main_display_loop.last_debug_time = current_time

        # Track if screen needs full redraw
        needs_full_redraw = False
        dirty_rects = []

        screen.fill((0, 0, 0))

        for i, camera_name in enumerate(camera_names):
            img_surface = current_state['images'].get(camera_name)
            last_update_ts = current_state['last_updated'].get(camera_name, 0)
            motion_state = current_state['motion_states'].get(camera_name, False)
            
            grid_pos = grid_positions[i]
            
            if img_surface:
                # Check if image has changed
                current_image_id = id(img_surface)
                if last_image_versions[camera_name] != current_image_id:
                    screen.blit(img_surface, grid_pos)
                    last_image_versions[camera_name] = current_image_id
                    dirty_rects.append(pygame.Rect(grid_pos[0], grid_pos[1], 
                                                   target_image_size[0], target_image_size[1]))
                else:
                    # Re-blit the same image (needed for full redraw)
                    screen.blit(img_surface, grid_pos)

                # Display loading text if necessary
                if last_update_ts == 0:
                    loading_text = f"Loading {camera_name}..."
                    text_surface = get_cached_text(loading_text, (255, 255, 255))
                    text_rect = text_surface.get_rect(
                        center=(grid_pos[0] + single_image_width // 2, 
                                grid_pos[1] + target_image_size[1] // 2)
                    )
                    screen.blit(text_surface, text_rect)
                
                # Display motion status (only update if changed)
                if last_motion_states[camera_name] != motion_state:
                    print(f"🎯 DISPLAY: {camera_name} motion state changed from {last_motion_states[camera_name]} to {motion_state}")
                    last_motion_states[camera_name] = motion_state
                    
                motion_status = "Motion ON" if motion_state else "Motion OFF"
                
                # Build status text
                if not is_mqtt_configured:
                    status_text = f"{camera_name}: {motion_status}{mqtt_off_suffix}"
                else:
                    status_text = f"{camera_name}: {motion_status}"

                status_color = (255, 255, 0) if motion_state else (0, 255, 0)
                status_surface = get_cached_text(status_text, status_color)
                screen.blit(status_surface, (grid_pos[0] + 10, grid_pos[1] + 10))

                # Conditionally display timestamp
                if show_timestamps and last_update_ts > 0:
                    current_ts_str = get_timestamp_string(last_update_ts)
                    
                    # Only update if timestamp changed
                    if current_ts_str and last_timestamps[camera_name] != current_ts_str:
                        last_timestamps[camera_name] = current_ts_str
                    
                    if current_ts_str:
                        timestamp_text = get_cached_text(current_ts_str, (255, 255, 255))
                        cell_right_edge = grid_pos[0] + single_image_width
                        timestamp_rect = timestamp_text.get_rect(
                            topright=(cell_right_edge - 10, grid_pos[1] + 10)
                        )
                        screen.blit(timestamp_text, timestamp_rect)

        # Update display
        pygame.display.flip()
        
        # Add small sleep to prevent excessive CPU usage
        time.sleep(0.01)  # 10ms sleep, allowing up to ~100 FPS when needed
        
        # Periodically clean text cache to prevent memory growth
        if len(text_cache) > 1000:
            # Keep only recent timestamp entries and commonly used text
            new_cache = {}
            current_time = int(time.time())
            for key, value in text_cache.items():
                if isinstance(key, tuple):  # Regular text cache entries
                    new_cache[key] = value
                elif isinstance(key, int) and current_time - key < 3600:  # Keep recent timestamps
                    new_cache[key] = value
            text_cache = new_cache
