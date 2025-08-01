import pygame
import datetime
import os
from frigate_manager import image_lock, current_images, camera_last_updated, camera_motion_states

def setup_display(config):
    """Initializes Pygame and sets up the screen."""
    pygame.init()
    display_resolution = tuple(config['display']['resolution'])
    screen = pygame.display.set_mode(display_resolution, pygame.FULLSCREEN | pygame.NOFRAME)
    pygame.mouse.set_visible(False)
    font_size = config['display']['font_size']
    font = pygame.font.Font(None, font_size)
    
    return screen, font

def display_splash_screen(screen, font, message, config):
    """
    Displays a splash screen with a given message and logo.
    
    Args:
        screen (pygame.Surface): The screen surface to draw on.
        font (pygame.font.Font): The font object to use for text.
        message (str): The message to display.
        config (dict): The application configuration.
    """
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

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_x:
                running = False

        screen.fill((0, 0, 0))

        with image_lock:
            for i, camera_name in enumerate(camera_names):
                img_surface = current_images.get(camera_name)
                if img_surface:
                    screen.blit(img_surface, grid_positions[i])

                    # Display loading/waiting text if necessary
                    if camera_last_updated[camera_name] == 0:
                         text_surface = font.render(f"Loading {camera_name}...", True, (255, 255, 255))
                         text_rect = text_surface.get_rect(center=(grid_positions[i][0] + single_image_width // 2, 
                                                                    grid_positions[i][1] + target_image_size[1] // 2))
                         screen.blit(text_surface, text_rect)
                    
                    # Display motion status
                    motion_status = "Motion ON" if camera_motion_states.get(camera_name, False) else "Motion OFF"
                    
                    # Add tertiary display if MQTT is not configured
                    if not is_mqtt_configured:
                        status_text = f"{camera_name}: {motion_status} (MQTT OFF)"
                    else:
                        status_text = f"{camera_name}: {motion_status}"

                    status_color = (255, 255, 0) if camera_motion_states.get(camera_name, False) else (0, 255, 0)
                    status_surface = font.render(status_text, True, status_color)
                    screen.blit(status_surface, (grid_positions[i][0] + 10, grid_positions[i][1] + 10))

                    # Conditionally display the timestamp
                    if show_timestamps:
                        last_update_ts = camera_last_updated.get(camera_name, 0)
                        if last_update_ts > 0:
                            timestamp_dt = datetime.datetime.fromtimestamp(last_update_ts)
                            timestamp_str = timestamp_dt.strftime("%H:%M:%S")
                            timestamp_text = font.render(timestamp_str, True, (255, 255, 255))
                            
                            cell_right_edge = grid_positions[i][0] + single_image_width
                            timestamp_rect = timestamp_text.get_rect(topright=(cell_right_edge - 10, grid_positions[i][1] + 10))
                            screen.blit(timestamp_text, timestamp_rect)

        pygame.display.flip()
