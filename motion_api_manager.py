import requests
import json
import time
import threading
from frigate_manager import image_lock, camera_intervals, camera_motion_states, wake_camera_thread

# Global state for manual motion toggles per camera
# Format: {camera_name: True/False/None} where None means "auto detect"
manual_motion_overrides = {}

def get_current_motion_states_from_frigate(config, session):
    """
    Query Frigate's API to get current motion detection states.
    This is used for initial sync and for API-only mode.
    """
    try:
        # Import api_token at runtime to avoid import issues
        from frigate_manager import api_token
        
        frigate_base_url = config['frigate']['base_url']
        camera_names = config['frigate']['camera_names']
        
        print(f"MOTION_API: Attempting to get motion states for cameras: {camera_names}")
        
        if not api_token:
            print("MOTION_API: No API token available, cannot query Frigate API")
            return False
            
        headers = {"Authorization": f"Bearer {api_token}"}
        
        # Get the latest events for each camera (no time filter - get the most recent)
        current_time = time.time()
        
        cameras_with_motion = set()
        
        # Check each camera individually to get their latest event
        for camera_name in camera_names:
            events_url = f"{frigate_base_url}/api/events"
            params = {
                "camera": camera_name,
                "limit": 1
            }
            
            try:
                response = session.get(events_url, headers=headers, params=params, verify=False, timeout=10)
                response.raise_for_status()
                
                events_data = response.json()
                
                if events_data:
                    latest_event = events_data[0]
                    label = latest_event.get('label', 'unknown')
                    start_time = latest_event.get('start_time', 0)
                    end_time = latest_event.get('end_time')
                    
                    # Calculate time since event started
                    time_since_start = current_time - start_time
                    
                    # Motion logic with expiry system:
                    # 1. If event is still active (no end_time), it's motion
                    # 2. If event ended within 15s grace period, keep motion ON
                    # 3. Otherwise, motion is OFF
                    
                    if not end_time:
                        # Event is still active
                        if time_since_start <= 60:  # Don't keep "stale" active events forever
                            cameras_with_motion.add(camera_name)
                    else:
                        # Event has ended, check if it's within grace period
                        time_since_end = current_time - end_time
                        grace_period = 15  # 15 second grace period after motion ends
                        
                        if time_since_end <= grace_period:
                            cameras_with_motion.add(camera_name)
                    
            except Exception as e:
                print(f"MOTION_API: Failed to get events for {camera_name}: {e}")
        
        # Update motion states based on detection + manual overrides
        changes_made = False
        with image_lock:
            for camera_name in camera_names:
                old_state = camera_motion_states.get(camera_name, False)
                
                # Check if there's a manual override for this camera
                manual_override = manual_motion_overrides.get(camera_name, None)
                
                if manual_override is not None:
                    # Manual override is active
                    new_state = manual_override
                else:
                    # Use automatic detection
                    new_state = camera_name in cameras_with_motion
                
                if old_state != new_state:
                    camera_motion_states[camera_name] = new_state
                    
                    if new_state:
                        camera_intervals[camera_name] = config['display']['interval_rate_max']
                    else:
                        camera_intervals[camera_name] = config['display']['interval_rate_min']
                    
                    changes_made = True
                    
                    # Wake up the camera thread for immediate response
                    wake_camera_thread(camera_name)
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"MOTION_API: HTTP request failed: {e}")
        return False
    except Exception as e:
        print(f"MOTION_API: Unexpected error: {e}")
        return False

def sync_initial_motion_state(config, session):
    """
    Get initial motion state from Frigate API on startup.
    This runs once after app initialization.
    """
    def delayed_sync():
        time.sleep(3)  # Wait for app to fully initialize
        
        try:
            success = get_current_motion_states_from_frigate(config, session)
            if success:
                print("Initial motion state sync completed")
            else:
                print("Initial motion state sync failed - continuing with defaults")
        except Exception as e:
            print(f"MOTION_API: Exception during initial sync: {e}")
    
    sync_thread = threading.Thread(target=delayed_sync, daemon=True)
    sync_thread.start()

def start_api_polling_mode(config, session):
    """
    Start continuous API polling for motion detection.
    This is used when MQTT is not available or api_only_mode is enabled.
    """
    def polling_loop():
        poll_interval = config['mqtt'].get('api_poll_interval', 2)
        print(f"API polling mode started (interval: {poll_interval}s)")
        
        while True:
            try:
                get_current_motion_states_from_frigate(config, session)
                time.sleep(poll_interval)
            except Exception as e:
                print(f"MOTION_API: Polling error: {e}")
                time.sleep(poll_interval * 2)  # Wait longer on error
    
    polling_thread = threading.Thread(target=polling_loop, daemon=True)
    polling_thread.start()

def set_manual_motion_override(camera_name, state):
    """
    Set manual motion override for a camera.
    
    Args:
        camera_name (str): Name of the camera
        state (bool or None): True=Force ON, False=Force OFF, None=Auto detect
    """
    global manual_motion_overrides
    
    # Import config to get interval values - we'll need this for immediate updates
    from config_manager import load_config
    config = load_config()
    
    if state is None:
        if camera_name in manual_motion_overrides:
            del manual_motion_overrides[camera_name]
        print(f"MOTION_API: {camera_name} manual override CLEARED - using auto detection")
    else:
        manual_motion_overrides[camera_name] = state
        state_text = "ON" if state else "OFF"
        print(f"MOTION_API: {camera_name} manual override set to {state_text}")
        
    # Immediately update the motion state AND intervals
    with image_lock:
        old_state = camera_motion_states.get(camera_name, False)
        if old_state != state:
            camera_motion_states[camera_name] = state
            
            # Update intervals immediately based on new state
            if state:
                camera_intervals[camera_name] = config['display']['interval_rate_max']
                print(f"MOTION_API: {camera_name} manually set to ON (fast interval)")
            else:
                camera_intervals[camera_name] = config['display']['interval_rate_min']
                print(f"MOTION_API: {camera_name} manually set to OFF (slow interval)")
                
    # Wake up the camera thread for immediate response
    wake_camera_thread(camera_name)

def get_manual_motion_overrides():
    """Get current manual overrides for all cameras."""
    return manual_motion_overrides.copy()

def toggle_camera_motion(camera_name):
    """
    Toggle motion state for a camera between OFF -> ON -> AUTO -> OFF...
    
    Returns:
        str: New state description ("ON (MANUAL)", "OFF (MANUAL)", "AUTO")
    """
    current_override = manual_motion_overrides.get(camera_name, None)
    current_auto_state = camera_motion_states.get(camera_name, False)
    
    if current_override is None:
        # Currently auto, set to opposite of current auto state
        new_state = not current_auto_state
        set_manual_motion_override(camera_name, new_state)
        return "ON (MANUAL)" if new_state else "OFF (MANUAL)"
    elif current_override == True:
        # Currently manual ON, set to manual OFF
        set_manual_motion_override(camera_name, False)
        return "OFF (MANUAL)"
    else:
        # Currently manual OFF, set to auto
        set_manual_motion_override(camera_name, None)
        return "AUTO"
