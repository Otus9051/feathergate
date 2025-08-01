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
    config = userdata['config']
    frigate_topic_prefix = config['mqtt']['frigate_topic_prefix']
    camera_names = config['frigate']['camera_names']
    
    topic_parts = msg.topic.split('/')
    expected_prefix_parts = frigate_topic_prefix.split('/')
    
    if len(topic_parts) == len(expected_prefix_parts) + 2 and \
       topic_parts[:len(expected_prefix_parts)] == expected_prefix_parts and \
       topic_parts[len(expected_prefix_parts) + 1] == 'motion': 
        
        camera_name_index = len(expected_prefix_parts) 
        camera_name = topic_parts[camera_name_index]
        
        if camera_name in camera_names:
            try:
                raw_payload = msg.payload.decode()
                payload = raw_payload.strip().upper() 
                
                with image_lock:
                    if payload == "ON": 
                        camera_intervals[camera_name] = config['display']['interval_rate_max']
                        camera_motion_states[camera_name] = True
                    elif payload == "OFF": 
                        camera_intervals[camera_name] = config['display']['interval_rate_min']
                        camera_motion_states[camera_name] = False
                    else:
                        print(f"[{camera_name}] Unrecognised payload: '{raw_payload}'. Expected 'ON' or 'OFF'.")
            except Exception as e:
                print(f"Error processing MQTT message for {camera_name}: {e}")
        else:
            print(f"Received MQTT message for unknown camera: {camera_name} from topic {msg.topic}")

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
