# scorer.py
# This script is responsible for assessing threat levels based on events
# received from various sources (e.g., Frigate, CodeProject.AI, Audio Service)
# via MQTT. It calculates a threat score and triggers alerts if the score
# exceeds a defined threshold.

import os
import json
import time
import paho.mqtt.client as mqtt
import logging

# --- Configuration from Environment Variables ---
try:
    # MQTT Configuration
    MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
    MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_FRIGATE_TOPIC = os.getenv("MQTT_FRIGATE_TOPIC", "frigate/events/#") # Topic for primary detection events
    MQTT_AUDIO_TOPIC = os.getenv("MQTT_AUDIO_TOPIC", "vz/audio/#") # Topic for audio analysis results
    MQTT_INQUIRY_TRIGGER_TOPIC_BASE = os.getenv("MQTT_INQUIRY_TRIGGER_TOPIC_BASE", "vz/inquiry") # Base topic to trigger audio inquiry
    MQTT_ALERT_TOPIC = os.getenv("MQTT_ALERT_TOPIC", "vz/alert") # Topic to publish alerts for other services (e.g. Home Assistant)

    # Scoring Configuration
    SCORE_THRESHOLD_ALARM = float(os.getenv("SCORE_THRESHOLD_ALARM", "0.8")) # Final threshold to trigger alarm
    SCORE_THRESHOLD_INQUIRY = float(os.getenv("SCORE_THRESHOLD_INQUIRY", "0.3")) # Threshold to trigger audio inquiry
    SCORE_BASE_PERSON = float(os.getenv("SCORE_BASE_PERSON", "0.2"))
    SCORE_BONUS_WEAPON = float(os.getenv("SCORE_BONUS_WEAPON", "0.5"))
    SCORE_BONUS_CLOTHING_MASK = float(os.getenv("SCORE_BONUS_CLOTHING_MASK", "0.1"))
    SCORE_BONUS_CLOTHING_HOODIE = float(os.getenv("SCORE_BONUS_CLOTHING_HOODIE", "0.1"))
    SCORE_BONUS_POSE_CROUCH_PRONE = float(os.getenv("SCORE_BONUS_POSE_CROUCH_PRONE", "0.15"))
    SCORE_AUDIO_NEGATIVE_TONE = float(os.getenv("SCORE_AUDIO_NEGATIVE_TONE", "0.3"))
    SCORE_AUDIO_THREAT_KEYWORDS = float(os.getenv("SCORE_AUDIO_THREAT_KEYWORDS", "0.2")) # e.g. "attack", "police"
    SCORE_AUDIO_EVASIVE_SILENCE = float(os.getenv("SCORE_AUDIO_EVASIVE_SILENCE", "0.1"))
    SCORE_AUDIO_CALM_DELIVERY = float(os.getenv("SCORE_AUDIO_CALM_DELIVERY", "-0.2")) # Negative score for known safe interactions

    # GPIO Configuration (if RPi.GPIO is to be used directly here)
    GPIO_PIN_ALARM = int(os.getenv("GPIO_PIN_ALARM", "17"))
    USE_GPIO = os.getenv("USE_GPIO", "true").lower() == "true"

    # Event Timeout (for pending audio inquiries)
    EVENT_TIMEOUT_SECONDS = int(os.getenv("EVENT_TIMEOUT_SECONDS", "60"))

except ValueError as e:
    logging.error(f"Error reading environment variable: {e}. Please check data types.")
    exit(1)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format=\'%(asctime)s - %(levelname)s - %(message)s\')

# --- GPIO Setup (Conditional) ---
if USE_GPIO:
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM) # Using Broadcom SOC channel numbers
        GPIO.setup(GPIO_PIN_ALARM, GPIO.OUT)
        GPIO.output(GPIO_PIN_ALARM, GPIO.LOW) # Ensure alarm is off initially
        logging.info(f"GPIO pin {GPIO_PIN_ALARM} initialized for alarm.")
    except ImportError:
        logging.warning("RPi.GPIO module not found. GPIO functionality will be disabled.")
        USE_GPIO = False
    except Exception as e:
        logging.error(f"Error initializing GPIO: {e}")
        USE_GPIO = False

# --- Global State ---
# Dictionary to store scores and timestamps for events pending audio feedback
# Key: event_id, Value: {"score": current_score, "timestamp": time.time(), "initial_data": event_data}
pending_events = {}

# --- MQTT Client Setup ---
mqtt_client = mqtt.Client()

# --- Helper Functions ---
def trigger_alarm(event_id, final_score, event_data):
    """Triggers the alarm system (GPIO and/or MQTT alert)."""
    alert_message = {
        "event_id": event_id,
        "final_score": final_score,
        "reason": "Threat score exceeded threshold.",
        "timestamp": time.time(),
        "original_event_data": event_data
    }
    logging.warning(f"ALARM TRIGGERED for event {event_id}! Score: {final_score}. Data: {event_data}")
    mqtt_client.publish(MQTT_ALERT_TOPIC, json.dumps(alert_message), qos=1)

    if USE_GPIO:
        try:
            GPIO.output(GPIO_PIN_ALARM, GPIO.HIGH)
            logging.info(f"GPIO pin {GPIO_PIN_ALARM} set to HIGH (Alarm ON).")
            # Potentially add logic to turn off alarm after a period, or via another MQTT command
        except Exception as e:
            logging.error(f"Error controlling GPIO for alarm: {e}")

def trigger_audio_inquiry(event_id, current_score, initial_event_data):
    """Publishes a message to trigger the audio inquiry service."""
    inquiry_topic = f"{MQTT_INQUIRY_TRIGGER_TOPIC_BASE}/{event_id}"
    payload = {
        "event_id": event_id,
        "current_score": current_score,
        "timestamp": time.time()
    }
    try:
        mqtt_client.publish(inquiry_topic, json.dumps(payload), qos=1)
        logging.info(f"Audio inquiry triggered for event {event_id} on topic {inquiry_topic}.")
        # Store event as pending audio feedback
        pending_events[event_id] = {
            "score": current_score,
            "timestamp": time.time(),
            "initial_data": initial_event_data
        }
    except Exception as e:
        logging.error(f"Failed to publish audio inquiry trigger for event {event_id}: {e}")

def calculate_initial_score(data):
    """Calculates the initial score based on Frigate/CPAI event data."""
    score = 0.0
    label = data.get("label", "")
    # Basic score for person detection
    if label == "person":
        score += SCORE_BASE_PERSON

    # Bonus for weapon detection (from Frigate or CPAI)
    # This assumes CPAI results might be merged into Frigate events or come as separate events
    # For simplicity, checking `data.get("attributes", {}).get("weapon")` or similar field
    if data.get("extras", {}).get("weapon") or data.get("attributes", {}).get("weapon"): # Compatibility with original script
        score += SCORE_BONUS_WEAPON
        logging.info(f"Weapon detected, adding bonus: {SCORE_BONUS_WEAPON}")

    # Example: Bonus for clothing attributes (if provided by CPAI and merged)
    clothing_attributes = data.get("attributes", {}).get("clothing", {})
    if clothing_attributes.get("mask"): # Assuming boolean
        score += SCORE_BONUS_CLOTHING_MASK
        logging.info(f"Mask detected, adding bonus: {SCORE_BONUS_CLOTHING_MASK}")
    if clothing_attributes.get("hoodie"):
        score += SCORE_BONUS_CLOTHING_HOODIE
        logging.info(f"Hoodie detected, adding bonus: {SCORE_BONUS_CLOTHING_HOODIE}")

    # Example: Bonus for pose (if provided by CPAI and merged)
    pose_attribute = data.get("attributes", {}).get("pose", "")
    if pose_attribute in ["crouch", "prone"]:
        score += SCORE_BONUS_POSE_CROUCH_PRONE
        logging.info(f"Pose 	"{pose_attribute}" detected, adding bonus: {SCORE_BONUS_POSE_CROUCH_PRONE}")

    # Add Frigate's confidence for the primary object if available and relevant
    # This needs careful tuning; raw confidence might not directly translate to threat.
    # For now, we rely on specific attribute bonuses.
    # score += data.get("confidence", 0.0) * 0.1 # Example: Small factor of Frigate confidence

    return round(score, 2)

# --- MQTT Callbacks ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Successfully connected to MQTT broker.")
        try:
            client.subscribe(MQTT_FRIGATE_TOPIC)
            logging.info(f"Subscribed to Frigate events: {MQTT_FRIGATE_TOPIC}")
            client.subscribe(MQTT_AUDIO_TOPIC)
            logging.info(f"Subscribed to Audio results: {MQTT_AUDIO_TOPIC}")
        except Exception as e:
            logging.error(f"Error subscribing to topics: {e}")
    else:
        logging.error(f"Failed to connect to MQTT broker, return code: {rc}")

def on_disconnect(client, userdata, rc):
    logging.warning(f"Disconnected from MQTT broker with result code {rc}. Attempting to reconnect...")
    # Implement reconnection logic if paho-mqtt doesn't handle it sufficiently by default
    # For now, relying on paho-mqtt's auto-reconnect if enabled, or eventual container restart.

def on_frigate_event(client, userdata, msg):
    """Handles incoming detection events from Frigate (and potentially CPAI)."""
    try:
        data = json.loads(msg.payload.decode())
        event_id = data.get("id")
        event_type = data.get("type", "unknown") # e.g., "new", "update", "end"

        logging.info(f"Received Frigate event ({event_type}) for ID {event_id}: {data}")

        # Process only new events or significant updates to avoid redundant scoring
        # The example focuses on initial detection and audio follow-up.
        # More complex state management per event_id might be needed for continuous updates.
        if event_type == "new" or (event_type == "update" and data.get("significant_change", False)):
            if not event_id:
                logging.warning("Event received without an ID. Skipping.")
                return

            # Clean up old pending events to prevent memory leaks
            cleanup_pending_events()

            if event_id in pending_events:
                logging.info(f"Event {event_id} is already pending audio inquiry. Ignoring new Frigate event for now.")
                return

            current_score = calculate_initial_score(data.get("after", {})) # Frigate events often have before/after
            logging.info(f"Initial score for event {event_id}: {current_score}")

            if current_score >= SCORE_THRESHOLD_ALARM:
                trigger_alarm(event_id, current_score, data.get("after", {}))
            elif current_score >= SCORE_THRESHOLD_INQUIRY:
                trigger_audio_inquiry(event_id, current_score, data.get("after", {}))
            else:
                logging.info(f"Event {event_id} score {current_score} is below inquiry threshold. No action.")

    except json.JSONDecodeError:
        logging.error(f"Failed to decode JSON from MQTT message: {msg.payload}")
    except Exception as e:
        logging.error(f"Error processing Frigate event: {e}")

def on_audio_result(client, userdata, msg):
    """Handles incoming audio analysis results from the audio service."""
    try:
        audio_data = json.loads(msg.payload.decode())
        event_id = audio_data.get("id")
        transcript = audio_data.get("transcript", "").lower()
        tone = audio_data.get("tone", "neutral").lower()

        logging.info(f"Received audio result for event {event_id}: {audio_data}")

        if not event_id:
            logging.warning("Audio result received without an event ID. Skipping.")
            return

        if event_id in pending_events:
            current_score = pending_events[event_id]["score"]
            initial_event_data = pending_events[event_id]["initial_data"]
            logging.info(f"Updating score for event {event_id} based on audio. Initial score: {current_score}")

            # Adjust score based on audio
            if tone == "negative":
                current_score += SCORE_AUDIO_NEGATIVE_TONE
                logging.info(f"Negative tone detected. Score +{SCORE_AUDIO_NEGATIVE_TONE}")
            
            # Example: Check for specific keywords
            if any(word in transcript for word in ["help", "police", "intruder", "attack"]):
                current_score += SCORE_AUDIO_THREAT_KEYWORDS
                logging.info(f"Threat keywords detected. Score +{SCORE_AUDIO_THREAT_KEYWORDS}")
            
            if "delivery" in transcript and tone != "negative": # e.g. "package delivery", "food delivery"
                current_score += SCORE_AUDIO_CALM_DELIVERY # Negative adjustment
                logging.info(f"Calm delivery mentioned. Score {SCORE_AUDIO_CALM_DELIVERY}")
            
            if not transcript.strip() and tone == "neutral": # Check for silence or non-committal response
                current_score += SCORE_AUDIO_EVASIVE_SILENCE
                logging.info(f"Evasive silence or no clear response. Score +{SCORE_AUDIO_EVASIVE_SILENCE}")

            current_score = round(current_score, 2)
            logging.info(f"Score for event {event_id} after audio analysis: {current_score}")

            if current_score >= SCORE_THRESHOLD_ALARM:
                trigger_alarm(event_id, current_score, initial_event_data)
            else:
                logging.info(f"Event {event_id} score {current_score} after audio is below alarm threshold. No alarm.")
            
            # Remove event from pending list after processing
            del pending_events[event_id]
        else:
            logging.warning(f"Received audio result for unknown or timed-out event ID: {event_id}. Ignoring.")

    except json.JSONDecodeError:
        logging.error(f"Failed to decode JSON from audio MQTT message: {msg.payload}")
    except Exception as e:
        logging.error(f"Error processing audio result: {e}")

def cleanup_pending_events():
    """Removes events from pending_events if they have timed out."""
    now = time.time()
    timed_out_ids = []
    for event_id, data in pending_events.items():
        if now - data["timestamp"] > EVENT_TIMEOUT_SECONDS:
            timed_out_ids.append(event_id)
            logging.info(f"Event {event_id} timed out waiting for audio response. Removing from pending.")
    
    for event_id in timed_out_ids:
        del pending_events[event_id]

# --- Main Execution ---
if __name__ == "__main__":
    logging.info("Starting Scorer Service...")

    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    # Using message_callback_add for topic-specific callbacks
    mqtt_client.message_callback_add(MQTT_FRIGATE_TOPIC, on_frigate_event)
    mqtt_client.message_callback_add(MQTT_AUDIO_TOPIC, on_audio_result)

    try:
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        mqtt_client.loop_forever() # Blocking call that processes network traffic, dispatches callbacks and handles reconnecting.
    except ConnectionRefusedError:
        logging.error(f"MQTT connection refused. Is the broker at {MQTT_HOST}:{MQTT_PORT} running and accessible?")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
    finally:
        if USE_GPIO:
            GPIO.cleanup() # Clean up GPIO resources on exit
        logging.info("Scorer service stopped.")

