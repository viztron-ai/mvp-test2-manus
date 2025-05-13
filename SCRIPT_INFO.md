# Basic Script Information

This document provides a brief overview of the main Python scripts within the Viztron Homebase MVP project, their purpose, key configuration options (via environment variables), and basic usage notes.

## 1. Scorer (`scripts/scorer.py`)

*   **Purpose:** This is the central threat assessment engine. It listens to MQTT events from vision (Frigate, CodeProject.AI) and audio services, calculates a threat score based on configurable rules, and can trigger an audio inquiry for ambiguous situations or a full alarm if a high threat is detected.
*   **Key Environment Variables:**
    *   `MQTT_HOST`, `MQTT_PORT`: MQTT broker connection details.
    *   `MQTT_FRIGATE_TOPIC`: Topic for Frigate detection events.
    *   `MQTT_AUDIO_TOPIC`: Topic for results from the audio service.
    *   `MQTT_INQUIRY_TRIGGER_TOPIC_BASE`: Base topic to trigger audio inquiries.
    *   `MQTT_ALERT_TOPIC`: Topic to publish high-priority alerts (e.g., for Home Assistant).
    *   `SCORE_THRESHOLD_ALARM`: Score at which a full alarm is triggered.
    *   `SCORE_THRESHOLD_INQUIRY`: Score at which an audio inquiry is triggered.
    *   `SCORE_BASE_PERSON`, `SCORE_BONUS_WEAPON`, etc.: Various weights for different detected events/attributes.
    *   `GPIO_PIN_ALARM`: BCM pin number for the physical alarm relay.
    *   `USE_GPIO`: Set to `true` to enable direct GPIO alarm control, `false` to disable (e.g., for testing without hardware).
    *   `EVENT_TIMEOUT_SECONDS`: How long to wait for an audio response before an event pending inquiry times out.
*   **Usage:** This script is intended to be run as a long-running service, typically within a Docker container. It automatically connects to MQTT and processes events.

## 2. Audio Service (`scripts/audio_service/audio_service.py`)

*   **Purpose:** Manages interactive audio. When triggered via MQTT, it plays a pre-recorded audio prompt, records the spoken response, transcribes it to text using the Whisper ASR model, performs basic sentiment/keyword analysis, and publishes the results back via MQTT.
*   **Key Environment Variables:**
    *   `MQTT_HOST`, `MQTT_PORT`: MQTT broker connection details.
    *   `MQTT_INQUIRY_LISTEN_TOPIC`: MQTT topic it listens to for inquiry triggers.
    *   `MQTT_AUDIO_RESULT_TOPIC_BASE`: Base MQTT topic for publishing its analysis results.
    *   `AUDIO_PROMPT_DIR`: Absolute path to the directory containing `.wav` audio prompt files (e.g., `/srv/prompts`).
    *   `AUDIO_RECORD_SECONDS`: Duration in seconds for audio recording.
    *   `AUDIO_RECORD_FILENAME_TMP`: Temporary path for saving recorded audio.
    *   `AUDIO_CHANNELS`, `AUDIO_RATE`: Recording parameters.
    *   `AUDIO_INPUT_DEVICE_INDEX`, `AUDIO_OUTPUT_DEVICE_INDEX`: (Optional) Specify ALSA/PulseAudio device indices if not using defaults.
    *   `WHISPER_MODEL_SIZE`: Specifies the Whisper model to use (e.g., `tiny-int8`, `base-int8`). `tiny-int8` is recommended for RPi5.
    *   `NEGATIVE_KEYWORDS`, `POSITIVE_KEYWORDS_CALM`: Comma-separated lists of keywords for basic sentiment analysis.
*   **Usage:** Designed to run as a service (e.g., in Docker). It requires access to audio hardware (microphone and speaker) and the directory of prompt files. Ensure `pyaudio` and `openai-whisper` Python packages and their system dependencies (like `libportaudio2`) are installed.

## 3. GPIO Relay Utility (`homebase/gpio_relay.py`)

*   **Purpose:** A utility script for direct control and testing of a GPIO pin connected to a relay. It can turn the pin ON (HIGH), OFF (LOW), or toggle it for a short duration.
*   **Key Environment Variables (for command-line default):**
    *   `GPIO_RELAY_PIN`: Sets the default GPIO pin if not specified via command-line argument.
*   **Command-Line Usage:**
    *   `python gpio_relay.py --pin <BCM_PIN_NUMBER> --state [on|off|toggle] [--delay <seconds>]`
    *   `python gpio_relay.py --test [--pin <BCM_PIN_NUMBER>]`: Runs a quick toggle test.
    *   Example: `python homebase/gpio_relay.py --pin 17 --state on`
*   **Notes:**
    *   This script can be run directly from the command line for testing hardware.
    *   It includes a simulation mode if the `RPi.GPIO` library is not found, allowing for testing logic without actual hardware.
    *   The primary alarm activation logic is now integrated into `scorer.py` (when `USE_GPIO=true`), making this script more of a standalone testing and utility tool.

This summary should help in understanding the roles and configurations of the core scripts in the project.
