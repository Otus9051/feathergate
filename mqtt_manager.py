import paho.mqtt.client as mqtt
from frigate_manager import image_lock, camera_intervals, camera_motion_states
import socket

def on_connect(client, userdata, flags, rc, properties):
    """Callback function for when the MQTT client connects."""
    if rc == 0:
        print("MQTT: Connected successfully.")
        config = userdata['config']
        frigate_topic_prefix = config['mqtt']['frigate_topic_prefix']
        camera_names = config['frigate']['camera_names']
        for camera in camera_names:
            topic = f"{frigate_topic_prefix}/{camera}/motion"
            client.subscribe(topic)
        print("MQTT: Subscribed to motion topics.")
    else:
        print(f"MQTT: Connection failed with code {rc}. Motion-based updates will not be available.")

def on_message(client, userdata, msg):
    """Callback function for when an MQTT message is received."""
    print(f"🚨 MQTT MESSAGE RECEIVED!")
    print(f"  Topic: {msg.topic}")
    print(f"  Payload: {msg.payload}")
    
    config = userdata['config']
    frigate_topic_prefix = config['mqtt']['frigate_topic_prefix']
    camera_names = config['frigate']['camera_names']
    
    print(f"  Config prefix: '{frigate_topic_prefix}'")
    print(f"  Config cameras: {camera_names}")
    
    topic_parts = msg.topic.split('/')
    expected_prefix_parts = frigate_topic_prefix.split('/')
    
    print(f"  Topic parts: {topic_parts}")
    print(f"  Expected prefix parts: {expected_prefix_parts}")
    
    # Debug the conditions
    condition1 = len(topic_parts) == len(expected_prefix_parts) + 2
    condition2 = topic_parts[:len(expected_prefix_parts)] == expected_prefix_parts
    condition3 = len(topic_parts) > len(expected_prefix_parts) + 1 and topic_parts[len(expected_prefix_parts) + 1] == 'motion'
    
    print(f"  Condition 1 (length {len(topic_parts)} == {len(expected_prefix_parts) + 2}): {condition1}")
    print(f"  Condition 2 (prefix match): {condition2}")
    print(f"  Condition 3 (motion suffix): {condition3}")
    
    if condition1 and condition2 and condition3:
        camera_name_index = len(expected_prefix_parts) 
        camera_name = topic_parts[camera_name_index]
        
        print(f"  ✅ Topic matches! Camera: '{camera_name}'")
        print(f"  Camera in config: {camera_name in camera_names}")
        
        if camera_name in camera_names:
            try:
                raw_payload = msg.payload.decode()
                payload = raw_payload.strip().upper() 
                
                print(f"  Raw payload: '{raw_payload}'")
                print(f"  Processed payload: '{payload}'")
                
                # Check current state before update
                with image_lock:
                    old_interval = camera_intervals.get(camera_name, 'unknown')
                    old_motion = camera_motion_states.get(camera_name, 'unknown')
                
                print(f"  Before update: interval={old_interval}, motion={old_motion}")
                
                with image_lock:
                    if payload == "ON": 
                        camera_intervals[camera_name] = config['display']['interval_rate_max']
                        camera_motion_states[camera_name] = True
                        print(f"  ✅ SET MOTION ON: interval={config['display']['interval_rate_max']}")
                    elif payload == "OFF": 
                        camera_intervals[camera_name] = config['display']['interval_rate_min']
                        camera_motion_states[camera_name] = False
                        print(f"  ✅ SET MOTION OFF: interval={config['display']['interval_rate_min']}")
                    else:
                        print(f"  ❌ Unrecognised payload: '{raw_payload}'. Expected 'ON' or 'OFF'.")
                
                # Check state after update
                with image_lock:
                    new_interval = camera_intervals.get(camera_name, 'unknown')
                    new_motion = camera_motion_states.get(camera_name, 'unknown')
                
                print(f"  After update: interval={new_interval}, motion={new_motion}")
                
            except Exception as e:
                print(f"  ❌ Error processing MQTT message for {camera_name}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"  ❌ Unknown camera: {camera_name} from topic {msg.topic}")
    else:
        print(f"  ❌ Topic doesn't match motion pattern - IGNORING")

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
        client.loop_forever() 
    except (socket.gaierror, ConnectionRefusedError) as e:
        print(f"MQTT: Connection failed: {e}. The MQTT thread will not run. Check your broker settings.")
    except Exception as e:
        print(f"MQTT: FATAL ERROR in mqtt_thread_loop: {e}. The MQTT thread will not run.")
    finally:
        client.disconnect()
