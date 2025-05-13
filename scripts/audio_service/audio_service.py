# audio_service.py
# This script provides an audio interaction service for the Homebase system.
# It listens for MQTT triggers, plays audio prompts, records responses,
# transcribes speech to text, performs basic sentiment/keyword analysis,
# and publishes the results back via MQTT.

import os
import json
import random
import time
import wave
import paho.mqtt.client as mqtt
import logging

# Attempt to import audio-related libraries
try:
    import pyaudio
    from whisper import load_model as load_whisper_model
except ImportError as e:
    logging.error(f"Missing critical audio dependency: {e}. Please install pyaudio and openai-whisper.")
    exit(1)

# --- Configuration from Environment Variables ---
try:
    # MQTT Configuration
    MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
    MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_INQUIRY_LISTEN_TOPIC = os.getenv("MQTT_INQUIRY_LISTEN_TOPIC", "vz/inquiry/#") # Topic to listen for inquiry triggers
    MQTT_AUDIO_RESULT_TOPIC_BASE = os.getenv("MQTT_AUDIO_RESULT_TOPIC_BASE", "vz/audio") # Base topic to publish audio results

    # Audio Configuration
    AUDIO_PROMPT_DIR = os.getenv("AUDIO_PROMPT_DIR", "/srv/prompts") # Directory containing .wav prompt files
    AUDIO_RECORD_SECONDS = int(os.getenv("AUDIO_RECORD_SECONDS", "5"))
    AUDIO_RECORD_FILENAME_TMP = os.getenv("AUDIO_RECORD_FILENAME_TMP", "/tmp/recorded_reply.wav")
    AUDIO_CHANNELS = int(os.getenv("AUDIO_CHANNELS", "1"))
    AUDIO_RATE = int(os.getenv("AUDIO_RATE", "16000"))
    AUDIO_FORMAT_PYAUDIO = pyaudio.paInt16 # Corresponds to 16-bit audio
    AUDIO_CHUNK_SIZE = int(os.getenv("AUDIO_CHUNK_SIZE", "2048"))
    AUDIO_INPUT_DEVICE_INDEX = os.getenv("AUDIO_INPUT_DEVICE_INDEX") # Optional: specify input device index
    AUDIO_OUTPUT_DEVICE_INDEX = os.getenv("AUDIO_OUTPUT_DEVICE_INDEX") # Optional: specify output device index

    # Whisper Model Configuration
    WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "tiny-int8") # e.g., tiny, base, small, medium (int8 for efficiency)

    # Sentiment/Keyword Analysis
    NEGATIVE_KEYWORDS = os.getenv("NEGATIVE_KEYWORDS", "angry,leave,attack,police,help,intruder,gun,knife,weapon").split(',')
    POSITIVE_KEYWORDS_CALM = os.getenv("POSITIVE_KEYWORDS_CALM", "delivery,package,mail,food,hello,hi,yes,okay").split(',')

except ValueError as e:
    logging.error(f"Error reading environment variable: {e}. Please check data types.")
    exit(1)
except Exception as e:
    logging.error(f"An unexpected error occurred during configuration: {e}")
    exit(1)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format=\'%(asctime)s - %(levelname)s - %(message)s\')

# --- Global Variables ---
py_audio_interface = None
whisper_model = None
available_prompts = []

# --- Helper Functions ---
def initialize_audio_system():
    """Initializes PyAudio and loads the Whisper model."""
    global py_audio_interface, whisper_model, available_prompts
    try:
        py_audio_interface = pyaudio.PyAudio()
        logging.info("PyAudio interface initialized.")

        # List available audio prompts
        if os.path.isdir(AUDIO_PROMPT_DIR):
            available_prompts = [f for f in os.listdir(AUDIO_PROMPT_DIR) if f.endswith(".wav")]
            if not available_prompts:
                logging.warning(f"No .wav prompt files found in {AUDIO_PROMPT_DIR}.")
            else:
                logging.info(f"Available audio prompts: {available_prompts}")
        else:
            logging.warning(f"Audio prompt directory {AUDIO_PROMPT_DIR} not found.")

        logging.info(f"Loading Whisper model: {WHISPER_MODEL_SIZE}...")
        whisper_model = load_whisper_model(WHISPER_MODEL_SIZE)
        logging.info("Whisper model loaded successfully.")
        return True

    except Exception as e:
        logging.error(f"Error initializing audio system: {e}")
        return False

def play_audio_prompt(prompt_filename):
    """Plays a specified .wav audio prompt."""
    if not py_audio_interface:
        logging.error("PyAudio not initialized. Cannot play audio.")
        return
    
    filepath = os.path.join(AUDIO_PROMPT_DIR, prompt_filename)
    if not os.path.exists(filepath):
        logging.error(f"Prompt file not found: {filepath}")
        return

    wf = None
    stream = None
    try:
        wf = wave.open(filepath, 'rb')
        output_device_index_int = int(AUDIO_OUTPUT_DEVICE_INDEX) if AUDIO_OUTPUT_DEVICE_INDEX else None
        stream = py_audio_interface.open(format=py_audio_interface.get_format_from_width(wf.getsampwidth()),
                                       channels=wf.getnchannels(),
                                       rate=wf.getframerate(),
                                       output=True,
                                       output_device_index=output_device_index_int)
        logging.info(f"Playing audio prompt: {filepath}")
        data = wf.readframes(AUDIO_CHUNK_SIZE)
        while data:
            stream.write(data)
            data = wf.readframes(AUDIO_CHUNK_SIZE)
        logging.info("Finished playing audio prompt.")
    except FileNotFoundError:
        logging.error(f"Audio prompt file not found: {filepath}")
    except Exception as e:
        logging.error(f"Error playing audio prompt {filepath}: {e}")
    finally:
        if stream:
            stream.stop_stream()
            stream.close()
        if wf:
            wf.close()

def record_audio_response():
    """Records audio from the microphone for a specified duration."""
    if not py_audio_interface:
        logging.error("PyAudio not initialized. Cannot record audio.")
        return None

    stream = None
    wf = None
    try:
        input_device_index_int = int(AUDIO_INPUT_DEVICE_INDEX) if AUDIO_INPUT_DEVICE_INDEX else None
        stream = py_audio_interface.open(format=AUDIO_FORMAT_PYAUDIO,
                                       channels=AUDIO_CHANNELS,
                                       rate=AUDIO_RATE,
                                       input=True,
                                       frames_per_buffer=AUDIO_CHUNK_SIZE,
                                       input_device_index=input_device_index_int)
        logging.info(f"Recording audio for {AUDIO_RECORD_SECONDS} seconds...")
        frames = []
        for _ in range(0, int(AUDIO_RATE / AUDIO_CHUNK_SIZE * AUDIO_RECORD_SECONDS)):
            data = stream.read(AUDIO_CHUNK_SIZE)
            frames.append(data)
        logging.info("Finished recording.")

        # Save the recorded data as a WAV file
        wf = wave.open(AUDIO_RECORD_FILENAME_TMP, 'wb')
        wf.setnchannels(AUDIO_CHANNELS)
        wf.setsampwidth(py_audio_interface.get_sample_size(AUDIO_FORMAT_PYAUDIO))
        wf.setframerate(AUDIO_RATE)
        wf.writeframes(b''.join(frames))
        logging.info(f"Recorded audio saved to {AUDIO_RECORD_FILENAME_TMP}")
        return AUDIO_RECORD_FILENAME_TMP

    except Exception as e:
        logging.error(f"Error recording audio: {e}")
        return None
    finally:
        if stream:
            stream.stop_stream()
            stream.close()
        if wf:
            wf.close()

def transcribe_audio(filepath):
    """Transcribes the audio file to text using Whisper."""
    if not whisper_model:
        logging.error("Whisper model not loaded. Cannot transcribe.")
        return None
    if not os.path.exists(filepath):
        logging.error(f"Audio file for transcription not found: {filepath}")
        return None
    try:
        logging.info(f"Transcribing audio file: {filepath}...")
        result = whisper_model.transcribe(filepath, fp16=False) # fp16=False for CPU, can be True for GPU
        transcript = result["text"].strip()
        logging.info(f"Transcription result: \"{transcript}\"")
        return transcript
    except Exception as e:
        logging.error(f"Error transcribing audio: {e}")
        return None

def analyze_transcript(transcript):
    """Performs basic sentiment/keyword analysis on the transcript."""
    if transcript is None:
        return "unknown", [] # Default tone and empty matched keywords

    text_lower = transcript.lower()
    matched_keywords = []
    tone = "neutral" # Default tone

    # Check for negative keywords
    for keyword in NEGATIVE_KEYWORDS:
        if keyword in text_lower:
            tone = "negative"
            matched_keywords.append(keyword)
            # If a strong negative keyword is found, no need to check for calm/positive ones
            logging.info(f"Negative keyword 	"{keyword}" found. Tone set to negative.")
            return tone, matched_keywords 

    # Check for calm/positive keywords if not already negative
    for keyword in POSITIVE_KEYWORDS_CALM:
        if keyword in text_lower:
            # Don't override if already negative, but can mark as neutral or positive if desired
            if tone != "negative": 
                tone = "neutral" # Or potentially "positive" if a separate category is needed
            matched_keywords.append(keyword)
            logging.info(f"Calm/positive keyword 	"{keyword}" found.")
            # Continue checking for other calm keywords

    if not transcript: # If transcript is empty (silence)
        tone = "silent" # Special tone for silence
        logging.info("Transcript is empty. Tone set to silent.")

    return tone, matched_keywords

# --- MQTT Callbacks ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Successfully connected to MQTT broker.")
        try:
            client.subscribe(MQTT_INQUIRY_LISTEN_TOPIC)
            logging.info(f"Subscribed to inquiry trigger topic: {MQTT_INQUIRY_LISTEN_TOPIC}")
        except Exception as e:
            logging.error(f"Error subscribing to topic: {e}")
    else:
        logging.error(f"Failed to connect to MQTT broker, return code: {rc}")

def on_disconnect(client, userdata, rc):
    logging.warning(f"Disconnected from MQTT broker with result code {rc}. Reconnection will be attempted by Paho.")

def on_inquiry_trigger(client, userdata, msg):
    """Handles incoming MQTT messages that trigger an audio inquiry."""
    try:
        payload_data = json.loads(msg.payload.decode())
        event_id = payload_data.get("event_id")
        logging.info(f"Received inquiry trigger for event ID: {event_id} from topic: {msg.topic}")

        if not event_id:
            logging.warning("Inquiry trigger received without an event_id. Skipping.")
            return

        if not available_prompts:
            logging.warning("No audio prompts available to play. Skipping inquiry.")
            # Optionally publish a status back indicating no prompts
            return

        # 1. Play a random audio prompt
        selected_prompt = random.choice(available_prompts)
        play_audio_prompt(selected_prompt)
        time.sleep(0.5) # Brief pause after prompt

        # 2. Record the response
        recorded_audio_path = record_audio_response()
        if not recorded_audio_path:
            logging.error("Audio recording failed. Cannot proceed with inquiry.")
            # Optionally publish a status back indicating recording failure
            return

        # 3. Transcribe the response
        transcript = transcribe_audio(recorded_audio_path)
        if transcript is None:
            logging.warning("Audio transcription failed or produced no text.")
            # Use empty string if transcription fails to allow tone analysis (e.g. for silence)
            transcript = "" 

        # 4. Analyze the transcript
        tone, matched_keywords = analyze_transcript(transcript)

        # 5. Publish the results
        result_payload = {
            "id": event_id,
            "transcript": transcript,
            "tone": tone,
            "matched_keywords": matched_keywords,
            "prompt_played": selected_prompt,
            "timestamp": time.time()
        }
        result_topic = f"{MQTT_AUDIO_RESULT_TOPIC_BASE}/{event_id}"
        client.publish(result_topic, json.dumps(result_payload), qos=1)
        logging.info(f"Published audio analysis result to {result_topic}: {result_payload}")

        # Clean up temporary recording file
        if os.path.exists(AUDIO_RECORD_FILENAME_TMP):
            try:
                os.remove(AUDIO_RECORD_FILENAME_TMP)
            except OSError as e:
                logging.warning(f"Could not remove temporary audio file {AUDIO_RECORD_FILENAME_TMP}: {e}")

    except json.JSONDecodeError:
        logging.error(f"Failed to decode JSON from inquiry trigger message: {msg.payload}")
    except Exception as e:
        logging.error(f"Error processing inquiry trigger: {e}")

# --- Main Execution ---
if __name__ == "__main__":
    logging.info("Starting Audio Interaction Service...")

    if not initialize_audio_system():
        logging.critical("Failed to initialize audio system. Exiting.")
        exit(1)

    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.message_callback_add(MQTT_INQUIRY_LISTEN_TOPIC, on_inquiry_trigger)

    try:
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        mqtt_client.loop_forever()
    except ConnectionRefusedError:
        logging.error(f"MQTT connection refused. Is the broker at {MQTT_HOST}:{MQTT_PORT} running?")
    except Exception as e:
        logging.critical(f"An unexpected error occurred in the main loop: {e}")
    finally:
        if py_audio_interface:
            py_audio_interface.terminate()
        logging.info("Audio Interaction Service stopped.")

