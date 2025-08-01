import paho.mqtt.client as mqtt
from frigate_manager import image_lock, camera_intervals, camera_motion_states
import socket
import threading
import time

# Global counter to track messages received
mqtt_message_count = 0

def on_connect(client, userdata, flags, rc, properties):
    """Callback function for when the MQTT client connects."""
    if rc == 0:
        print("MQTT: Connected successfully.")
        config = userdata['config']
        frigate_topic_prefix = config['mqtt']['frigate_topic_prefix']
        camera_names = config['frigate']['camera_names']
        
        # Subscribe to motion topics with QoS 1 to ensure message delivery
        for camera in camera_names:
            motion_topic = f"{frigate_topic_prefix}/{camera}/motion"
            client.subscribe(motion_topic, qos=1)
            print(f"MQTT: Subscribed to {motion_topic}")
        
        print("MQTT: Subscribed to all motion topics.")
        
        # Show current motion states after connection
        with image_lock:
            print("MQTT: Current motion states after connection:")
            for camera_name in camera_names:
                motion_state = camera_motion_states.get(camera_name, False)
                interval = camera_intervals.get(camera_name, config['display']['interval_rate_min'])
                print(f"  {camera_name}: motion={motion_state}, interval={interval}")
        
    else:
        print(f"MQTT: Connection failed with code {rc}. Motion-based updates will not be available.")

def on_message(client, userdata, msg):
    """Callback function for when an MQTT message is received."""
    global mqtt_message_count
    mqtt_message_count += 1
    
    try:
        topic = msg.topic
        decoded_payload = msg.payload.decode() if msg.payload else ""
        
        config = userdata['config']
        frigate_topic_prefix = config['mqtt']['frigate_topic_prefix']
        camera_names = config['frigate']['camera_names']
        
        # Parse topic to extract camera name
        topic_parts = topic.split('/')
        expected_prefix_parts = frigate_topic_prefix.split('/')
        
        # Check if this is a motion topic for one of our cameras
        if (len(topic_parts) == len(expected_prefix_parts) + 2 and
            topic_parts[:len(expected_prefix_parts)] == expected_prefix_parts and
            topic_parts[-1] == 'motion'):
            
            camera_name = topic_parts[len(expected_prefix_parts)]
            
            if camera_name in camera_names:
                payload = decoded_payload.strip().upper()
                
                # Get current state before update
                with image_lock:
                    old_motion = camera_motion_states.get(camera_name, False)
                
                # Update state
                with image_lock:
                    if payload == "ON":
                        camera_motion_states[camera_name] = True
                        camera_intervals[camera_name] = config['display']['interval_rate_max']
                        print(f"MQTT: {camera_name} MOTION ON")
                    elif payload == "OFF":
                        camera_motion_states[camera_name] = False
                        camera_intervals[camera_name] = config['display']['interval_rate_min']
                        print(f"MQTT: {camera_name} MOTION OFF")
                    else:
                        print(f"MQTT: Unknown payload '{payload}' for {camera_name}")
                        return
                
                # Show state change if it occurred
                new_motion = camera_motion_states.get(camera_name, False)
                if old_motion != new_motion:
                    print(f"MQTT: {camera_name} state changed: {old_motion} -> {new_motion}")
                
            else:
                print(f"MQTT: Unknown camera '{camera_name}' in topic {topic}")
        else:
            # Only show non-motion messages occasionally to avoid spam
            if mqtt_message_count % 50 == 1:  # Show every 50th non-motion message
                print(f"MQTT: Non-motion message #{mqtt_message_count}: {topic}")
            
    except Exception as e:
        print(f"MQTT: Error processing message: {e}")
        import traceback
        traceback.print_exc()

def mqtt_thread_loop(config):
    """
    Main loop for the MQTT client.
    """
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, userdata={'config': config})
    client.on_connect = on_connect
    client.on_message = on_message

    if config.get('mqtt', {}).get('username') and config.get('mqtt', {}).get('password'):
        client.username_pw_set(config['mqtt']['username'], config['mqtt']['password'])

    try:
        client.connect(config['mqtt']['broker_host'], config['mqtt']['broker_port'], 60)
        
        # Start a periodic state reporter in a separate thread
        def periodic_state_reporter():
            while True:
                time.sleep(30)  # Report every 30 seconds
                with image_lock:
                    active_cameras = []
                    for camera_name in config['frigate']['camera_names']:
                        motion_state = camera_motion_states.get(camera_name, False)
                        if motion_state:
                            active_cameras.append(camera_name)
                    
                    if active_cameras:
                        print(f"MQTT: Cameras with active motion: {', '.join(active_cameras)} (total messages: {mqtt_message_count})")
                    else:
                        print(f"MQTT: No active motion detected (total messages: {mqtt_message_count})")
        
        reporter_thread = threading.Thread(target=periodic_state_reporter, daemon=True)
        reporter_thread.start()
        
        print("MQTT: Starting main loop...")
        client.loop_forever() 
    except (socket.gaierror, ConnectionRefusedError) as e:
        print(f"MQTT: Connection failed: {e}. The MQTT thread will not run. Check your broker settings.")
    except Exception as e:
        print(f"MQTT: FATAL ERROR in mqtt_thread_loop: {e}. The MQTT thread will not run.")
    finally:
        client.disconnect()
