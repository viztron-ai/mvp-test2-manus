# Architecture Review and Improvement Proposals

## Current Architecture Overview

The Homebase system, as outlined in the provided documents, is designed as a modular, Docker-based application running on a Raspberry Pi 5 with a Coral Edge TPU. Key components include:

1.  **Input Processing (Vision):**
    *   **Frigate:** Handles primary video stream processing, object detection (persons, vehicles, packages) using the Coral TPU (e.g., YOLOv5n model). Publishes detection events to MQTT.
    *   **CodeProject.AI (CPAI):** Performs secondary, more detailed analysis (e.g., weapon detection, clothing analysis, pose estimation) on images/frames, likely triggered by Frigate events or specific requests. Also integrates via MQTT or HTTP.

2.  **Input Processing (Audio - Proposed):**
    *   **Audio Service:** A dedicated Docker container to manage audio interaction. It will:
        *   Play pre-recorded audio prompts (e.g., "Identify yourself").
        *   Record audio responses.
        *   Transcribe speech-to-text using a lightweight model (e.g., Whisper-tiny-int8).
        *   Perform basic sentiment/keyword analysis on the transcript.
        *   Publish audio analysis results (transcript, tone) to MQTT.

3.  **Communication Bus:**
    *   **Mosquitto MQTT Broker:** Serves as the central messaging system for inter-service communication (Frigate events, CPAI results, audio service data, scorer commands).

4.  **Core Logic & Threat Assessment:**
    *   **Scorer (`scorer.py`):** A Python script running in its own Docker container. It:
        *   Subscribes to MQTT topics for detection events (from Frigate, CPAI, and potentially the audio service).
        *   Calculates a threat score based on detected objects, attributes, and audio feedback.
        *   Triggers actions (e.g., activate siren via GPIO) if the threat score exceeds a threshold.
        *   Potentially initiates audio inquiries via MQTT if an initial score is in an intermediate range.

5.  **Hardware Interaction & System Services:**
    *   **`homebase/` utilities:** Contains scripts for direct hardware control and system-level services:
        *   `gpio_relay.py`: Toggles GPIO pins (e.g., for a siren).
        *   `lte_failover.service`: Systemd service for LTE backup internet.
        *   `ups_shutdown.service`: Systemd service for graceful shutdown on UPS low battery.

6.  **Configuration:**
    *   `docker-compose.yml`: Defines and orchestrates all services.
    *   `frigate.yml`: Configures Frigate (cameras, detectors, MQTT).
    *   `modules.json`: Configures models for CodeProject.AI.
    *   `scorer.env`: Environment variables for the scorer script (threshold, MQTT host, GPIO pin).

7.  **User Interface (Optional):**
    *   **Home Assistant:** Can be added as an optional UI layer for system monitoring, device control, and mobile push notifications (potentially via Nabu Casa for cloud access).

8.  **Deployment & Management:**
    *   Git repository for version control and easy deployment.
    *   README.md for setup and usage instructions.

## Proposed Improvements & Refinements

Based on the review and your requirements, here are some proposed improvements to enhance the system's efficiency, robustness, and functionality:

1.  **Refined Threat Scoring Logic in `scorer.py`:**
    *   **Stateful Scoring:** Implement a mechanism (e.g., a dictionary mapping event IDs to scores) to allow scores to be accumulated for a single event across multiple inputs (e.g., initial visual detection followed by audio interaction results). This is crucial for the audio inquiry feature to correctly modify an existing event's threat level.
    *   **Configurable Scoring Weights:** Instead of hardcoding score increments (e.g., `score += 0.5` for a weapon), consider making these weights configurable, perhaps through `scorer.env` or a separate JSON configuration file. This would allow for easier tuning of the threat assessment logic.

2.  **Enhanced IoT Device Command Structure:**
    *   **Standardized MQTT Topics for Actions:** If the system needs to control more IoT devices beyond the siren, define a clear and extensible MQTT topic structure for commands (e.g., `homebase/command/light/on`, `homebase/command/door/lock`). The `scorer.py` or other logic modules can then publish to these topics.
    *   **Consider Home Assistant for Broader IoT:** If extensive IoT control is a goal, leveraging the optional Home Assistant integration more centrally could simplify managing diverse devices and their states.

3.  **AWS Greengrass Integration Clarification & Strategy:**
    *   **Clarify Requirement:** The initial request mentioned "relay information to app/cloud (GreenGrass hub)". We need to clarify if AWS IoT Greengrass integration is a firm requirement for this MVP or a future goal. This has significant architectural implications.
    *   **Potential Strategies (if required):**
        *   **MQTT Bridge:** Configure Mosquitto to bridge relevant topics to AWS IoT Core, which Greengrass can then interact with.
        *   **Direct Greengrass Component:** Develop a custom Greengrass component that subscribes to the local Mosquitto broker or runs some of the existing Python logic directly within the Greengrass environment.
        *   **Greengrass as Primary Broker:** Potentially use the Greengrass Core's local MQTT broker instead of Mosquitto, requiring services to publish/subscribe there.
    *   This needs to be decided before significant code changes are made if it's in scope for the current task.

4.  **Camera Processing and Performance (Frigate):**
    *   **FPS Clarification:** The knowledge item `user_4` mentions "Camera FPS must be at least 20 FPS", while the example `frigate.yml` has `detect: fps: 5`. It's important to understand that Frigate's `detect.fps` is the rate at which Frigate processes frames for object detection, not necessarily the camera's raw stream FPS. A lower detection FPS (e.g., 5-10 FPS) is common to save resources on devices like the RPi5, especially when also recording at a higher FPS. We should confirm if 5-10 FPS for *detection* is acceptable, assuming the camera itself streams at 20+ FPS for recording purposes. The RPi5 with a Coral TPU should be capable of handling this.

5.  **Audio Service Enhancements:**
    *   **Configurable Audio Device:** Make the audio hardware interface (e.g., `hw:1,0` in `docker-compose.yml` for the audio service) configurable via an environment variable. This will simplify setup on different Raspberry Pi boards or with different USB audio devices where the device index might vary.
    *   **Robust Audio File Handling:** Ensure paths to audio prompt files are correctly managed and potentially make them configurable if they are likely to change.

6.  **Code Quality, Comments, and Error Handling:**
    *   **Comprehensive Comments:** Add detailed comments to all Python scripts (`scorer.py`, `gpio_relay.py`, `audio_service.py`, and any new scripts) explaining the purpose of functions, complex logic, and configuration parameters, as per your request.
    *   **Error Handling:** Implement more robust error handling (e.g., `try-except` blocks) in all Python scripts, especially for:
        *   Network operations (MQTT connections, publishing, subscribing).
        *   Hardware interactions (GPIO setup and control).
        *   File I/O (reading configs, loading models, accessing audio files).
        *   Graceful recovery or logging upon failure.

7.  **Security Considerations (Future MVP Iteration):**
    *   For a production security system, MQTT communication should be secured (e.g., using username/password authentication and TLS encryption), especially if any part of the MQTT traffic leaves the local device or a trusted network. This can be considered for a later iteration if not critical for the immediate MVP.

8.  **Documentation Expansion:**
    *   **Detailed README:** Ensure the `README.md` is comprehensive, covering the setup of all components including the audio service, configuration of scoring parameters (if made configurable), and troubleshooting tips.
    *   **Executive and Technical Summaries:** Prepare these as requested, detailing what the system does, the architecture, and the changes/improvements made.

These proposals aim to build upon the solid foundation of the current MVP design, making it more robust, configurable, and aligned with the full set of requirements.
