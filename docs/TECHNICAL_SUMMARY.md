# Technical Summary: Viztron Homebase MVP

## Date: May 13, 2025

## 1. Introduction

This document provides a technical summary of the Viztron Homebase Minimum Viable Product (MVP). It details each module within the system, its architecture, responsibilities, configuration, and integration points. The system is designed to run on a Raspberry Pi 5 with a Coral Edge TPU, utilizing Docker for containerization and MQTT for inter-service communication.

The primary goal is to provide an intelligent home security solution capable of visual and audio threat assessment, leading to automated actions like inquiries or alarms.

## 2. Overall System Architecture

The system employs a microservices-like architecture orchestrated by Docker Compose. Key components communicate primarily via an MQTT message broker. This decoupled design allows for modularity, scalability, and easier maintenance.

**Core Technologies:**
*   **Hardware:** Raspberry Pi 5 (16GB recommended), Coral M.2 Dual Edge TPU.
*   **OS:** Raspberry Pi OS (or similar Debian-based Linux).
*   **Containerization:** Docker, Docker Compose.
*   **Messaging:** Mosquitto MQTT Broker.
*   **AI/Vision:** Frigate (with Edge TPU), CodeProject.AI.
*   **Audio Processing:** PyAudio, Whisper (for ASR).
*   **Core Logic:** Python 3.10+.

**File Structure Root:** `viztron_mvp_refactored/` (Refer to `docs/FILE_STRUCTURE_DESIGN.md` for full details)

## 3. Module Breakdown

### 3.1. Docker Compose Orchestration
*   **File:** `compose/docker-compose.yml`
*   **Purpose:** Defines and manages the lifecycle of all containerized services in the application. It specifies container images, ports, volumes, environment variables, dependencies, and restart policies.
*   **Key Services Defined:**
    *   `mosquitto`: MQTT broker.
    *   `frigate`: Primary video processing and object detection.
    *   `codeprojectai`: Advanced AI analysis (optional, for specific models).
    *   `scorer`: Core threat scoring and decision logic.
    *   `audio_service`: Handles audio interaction (prompts, recording, ASR).
    *   (Optional) `homeassistant`: UI and broader IoT integration layer.
*   **Integration:** Orchestrates the entire stack, ensuring services can communicate via the defined network (typically a default Docker bridge network) and access necessary configurations and hardware.
*   **Configuration:** Primarily through the `docker-compose.yml` file itself. Environment variables for individual services are often passed via `env_file` directives or directly in the compose file.

### 3.2. Mosquitto (MQTT Broker)
*   **Docker Image:** `eclipse-mosquitto` (or similar)
*   **Purpose:** Acts as the central communication hub. Services publish messages to specific topics, and other services subscribe to these topics to receive information.
*   **Key Topics (Conceptual - actual topics defined by services):
    *   `frigate/events/#`: Frigate publishes object detection events here.
    *   `vz/inquiry/{event_id}`: Scorer publishes to trigger audio service for a specific event.
    *   `vz/audio/{event_id}`: Audio service publishes transcription and analysis results.
    *   `vz/alert`: Scorer publishes high-priority alerts (e.g., for alarm or Home Assistant).
*   **Integration:** All Python services (`scorer.py`, `audio_service.py`) and Frigate connect to this broker.
*   **Configuration:** Basic configuration is handled by the Docker image defaults. Port 1883 is typically exposed.

### 3.3. Frigate (Primary Vision Processing)
*   **Docker Image:** `blakeblackshear/frigate:stable`
*   **Purpose:** Real-time NVR (Network Video Recorder) with AI-powered object detection. It processes RTSP streams from cameras, utilizes the Coral Edge TPU for efficient detection (persons, cars, etc.), and publishes events to MQTT.
*   **Configuration:**
    *   **Main Config:** `config/frigate.yml` (mounted into the container). Defines MQTT settings, camera inputs, detector types (Edge TPU), zones, recording settings, etc.
    *   **TPU Access:** Requires passthrough of Edge TPU devices (e.g., `/dev/apex_0`, `/dev/apex_1`) in `docker-compose.yml`.
*   **Integration:**
    *   **Input:** RTSP streams from IP cameras.
    *   **Output:** Publishes detection events (JSON payload) to `frigate/events/#` on MQTT.
    *   **Hardware:** Utilizes Coral Edge TPU for detection, RPi5 CPU/GPU for video decoding/encoding.
*   **Dependencies:** IP cameras, Coral Edge TPU.

### 3.4. CodeProject.AI (Secondary/Advanced Vision Processing)
*   **Docker Image:** `codeproject/ai-server:latest`
*   **Purpose:** Provides a platform for running various AI models. In this MVP, it can be used for more specialized detections not covered by Frigate (e.g., specific weapon models, advanced clothing analysis, pose estimation) if such models are configured.
*   **Configuration:**
    *   **Model Config:** `config/modules.json` (mounted into the container). Defines which AI modules/models are enabled.
    *   Potentially requires TPU access if using TPU-compatible models and Frigate isn't monopolizing them.
*   **Integration:**
    *   **Input:** Typically receives images/frames for analysis via HTTP API calls, potentially triggered by Frigate events or the scorer service.
    *   **Output:** Returns analysis results (JSON) via HTTP. Could also be configured to publish to MQTT.
*   **Note:** Its role in the current refactored MVP is more as an optional extension for deeper analysis. The primary scoring logic in `scorer.py` mainly expects events from Frigate but can be extended.

### 3.5. Scorer Service (`scorer.py`)
*   **Location:** `scripts/scorer.py`
*   **Docker Image:** `python:3.10-slim` (or similar, with dependencies installed)
*   **Purpose:** The core decision-making engine. It subscribes to MQTT topics for events from Frigate and the Audio Service. It calculates a threat score based on configurable rules and event attributes. Based on the score, it can trigger an audio inquiry or a full alarm (via GPIO and/or MQTT alert).
*   **Configuration (Environment Variables - see `scripts/scorer.env.example`):
    *   MQTT connection details and topics (`MQTT_HOST`, `MQTT_FRIGATE_TOPIC`, `MQTT_AUDIO_TOPIC`, etc.).
    *   Scoring thresholds (`SCORE_THRESHOLD_ALARM`, `SCORE_THRESHOLD_INQUIRY`).
    *   Score weights for various events/attributes (`SCORE_BASE_PERSON`, `SCORE_BONUS_WEAPON`, etc.).
    *   GPIO pin for alarm (`GPIO_PIN_ALARM`) and enable flag (`USE_GPIO`).
    *   Event timeout for pending audio inquiries (`EVENT_TIMEOUT_SECONDS`).
*   **Integration:**
    *   **Input:** Subscribes to `MQTT_FRIGATE_TOPIC` and `MQTT_AUDIO_TOPIC`.
    *   **Output:**
        *   Publishes to `MQTT_INQUIRY_TRIGGER_TOPIC_BASE/{event_id}` to trigger audio service.
        *   Publishes to `MQTT_ALERT_TOPIC` for high-priority alerts.
        *   Controls GPIO pin `GPIO_PIN_ALARM` if `USE_GPIO` is true.
*   **Dependencies:** `paho-mqtt`, `RPi.GPIO` (optional).

### 3.6. Audio Service (`audio_service.py`)
*   **Location:** `scripts/audio_service/audio_service.py`
*   **Docker Image:** `python:3.10-slim` (or similar, with dependencies from `requirements.txt` installed)
*   **Purpose:** Manages interactive audio dialogues. When triggered by an MQTT message (from the Scorer), it plays a pre-recorded audio prompt, records the response using a microphone, transcribes the speech to text using a local Whisper ASR model, performs basic sentiment/keyword analysis, and publishes the results back via MQTT.
*   **Configuration (Environment Variables - see `scripts/audio_service/audio_service.env.example`):
    *   MQTT connection details and topics (`MQTT_HOST`, `MQTT_INQUIRY_LISTEN_TOPIC`, etc.).
    *   Audio settings (`AUDIO_PROMPT_DIR`, `AUDIO_RECORD_SECONDS`, device indices, etc.).
    *   Whisper model size (`WHISPER_MODEL_SIZE`).
    *   Keywords for analysis (`NEGATIVE_KEYWORDS`, `POSITIVE_KEYWORDS_CALM`).
*   **Integration:**
    *   **Input:** Subscribes to `MQTT_INQUIRY_LISTEN_TOPIC`.
    *   **Output:** Publishes analysis results (JSON payload containing transcript, tone, event ID) to `MQTT_AUDIO_RESULT_TOPIC_BASE/{event_id}`.
*   **Dependencies:** `paho-mqtt`, `pyaudio`, `openai-whisper`. Requires system libraries like `libportaudio2`. Needs access to audio hardware (microphone, speaker) and prompt files.
*   **Prompt Files:** Expects `.wav` files in the directory specified by `AUDIO_PROMPT_DIR` (e.g., `/srv/prompts/` inside the container).

### 3.7. Homebase Utilities
*   **Location:** `homebase/`
*   **Purpose:** Contains scripts and service files for direct Raspberry Pi hardware interaction or host-level system services. These are typically not part of the core Dockerized application logic but provide essential support functions.
*   **Components:**
    *   **`gpio_relay.py`:** A Python utility script for direct command-line testing and control of a GPIO pin. Can be used to verify relay functionality.
    *   **`lte_failover.service.example`:** Example systemd unit file for setting up LTE failover on the host RPi.
    *   **`ups_shutdown.service.example`:** Example systemd unit file for graceful shutdown triggered by a UPS.
*   **Integration:** These utilities interact directly with the RPi's OS and hardware. `gpio_relay.py` uses `RPi.GPIO`. Systemd services are managed by the host's systemd.

### 3.8. Configuration Files
*   **Purpose:** Provide user-configurable settings for various services without modifying code.
*   **Key Files (examples provided, users create actual files):
    *   `config/frigate.yml` (from `frigate.yml.example`)
    *   `config/modules.json` (from `modules.json.example` for CPAI)
    *   `scripts/scorer.env` (from `scorer.env.example`)
    *   `scripts/audio_service/audio_service.env` (from `audio_service.env.example`)
*   **Management:** Example files are included in the Git repository. Users copy and customize them. These files are then mounted into the respective Docker containers or used to provide environment variables.

### 3.9. Documentation
*   **Location:** `docs/`
*   **Purpose:** Provides comprehensive information about the project.
*   **Key Documents:**
    *   `README.md` (root level): Main project overview, setup, usage.
    *   `EXECUTIVE_SUMMARY.md`: High-level summary for non-technical stakeholders.
    *   `TECHNICAL_SUMMARY.md` (this document): Detailed module breakdown.
    *   `ARCHITECTURE.md`: System architecture and design choices.
    *   `SCRIPT_INFO.md`: Overview of main Python scripts.
    *   `HARDWARE_SOFTWARE.md`: Hardware/software stack details.
    *   `VALIDATION_REPORT.md`: Script validation results.
    *   `FILE_STRUCTURE_DESIGN.md`: Overview of the repository layout.

## 4. Data Flow Example (Threat Scenario)

1.  **Camera** captures an event (e.g., person detected in yard).
2.  **Frigate** processes the video stream, detects the person using the Coral TPU, and publishes an event to `frigate/events/{event_id}` on MQTT.
3.  **Scorer Service** receives the Frigate event. Calculates an initial score. If the score is above `SCORE_THRESHOLD_INQUIRY` but below `SCORE_THRESHOLD_ALARM`:
    *   It publishes a message to `vz/inquiry/{event_id}` to trigger the Audio Service.
    *   Stores the event details and current score in its `pending_events` dictionary.
4.  **Audio Service** receives the inquiry trigger:
    *   Plays a random audio prompt (e.g., "Identify yourself.").
    *   Records the response.
    *   Transcribes the audio to text using Whisper.
    *   Analyzes the transcript for tone/keywords.
    *   Publishes the result (transcript, tone) to `vz/audio/{event_id}`.
5.  **Scorer Service** receives the audio result:
    *   Retrieves the pending event details for `{event_id}`.
    *   Adjusts the score based on the audio analysis (e.g., increases score for negative tone, decreases for calm delivery explanation).
    *   If the new score exceeds `SCORE_THRESHOLD_ALARM`, it triggers an alarm (e.g., activates GPIO pin, publishes to `vz/alert`).
    *   Removes the event from `pending_events`.

## 5. Conclusion

The Viztron Homebase MVP, with its refactored components, provides a robust and extensible platform for intelligent home security. The modular design, reliance on MQTT, and clear separation of concerns allow for future enhancements and integrations. The system is well-documented and structured for ease of deployment and maintenance on the target Raspberry Pi 5 hardware.
