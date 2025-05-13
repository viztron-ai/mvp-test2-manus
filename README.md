# Viztron Homebase MVP (Refactored)

## Project Overview

This project provides a refactored and enhanced Minimum Viable Product (MVP) for the Viztron Homebase system. It is an intelligent home security solution designed to run on a Raspberry Pi 5 with a Coral Edge TPU. The system processes camera feeds, performs AI-powered threat detection (visual and audio), and can trigger actions like audio inquiries or alarms.

For a high-level overview, please see `docs/EXECUTIVE_SUMMARY.md`.
For detailed technical information, please see `docs/TECHNICAL_SUMMARY.md`.

## Key Features

*   **Modular Architecture:** Uses Docker and Docker Compose for easy management of services (Frigate, CodeProject.AI, Scorer, Audio Service, MQTT Broker).
*   **AI-Powered Vision:** Leverages Frigate and Coral Edge TPU for primary object detection. CodeProject.AI can be used for secondary, more advanced analysis.
*   **Interactive Audio Inquiry:** A dedicated audio service can play prompts, record responses, transcribe speech-to-text (using Whisper), and perform basic sentiment analysis.
*   **Advanced Threat Scoring:** A central scorer script evaluates events from vision and audio services, calculates a threat score, and makes decisions based on configurable thresholds.
*   **Hardware Integration:** Supports GPIO control for alarms and includes examples for LTE failover and UPS shutdown services.
*   **Configurable:** Most parameters are configurable via environment variables or dedicated configuration files.
*   **Comprehensive Documentation:** Includes detailed architecture, script information, hardware/software considerations, and setup guides.

## File Structure

A detailed file structure overview can be found in `docs/FILE_STRUCTURE_DESIGN.md`. Here is a summary:

```
viztron_mvp_refactored/
├── compose/                    # Docker Compose files
│   └── docker-compose.yml
├── config/                     # Example configuration files for services
│   ├── frigate.yml.example
│   └── modules.json.example
├── scripts/                    # Core application scripts
│   ├── scorer.py
│   ├── scorer.env.example
│   └── audio_service/          # Audio interaction service components
│       ├── audio_service.py
│       ├── requirements.txt
│       ├── audio_service.env.example
│       └── prompts/            # Example .wav audio prompts
├── homebase/                   # Utility scripts for RPi hardware interaction
│   ├── gpio_relay.py
│   ├── lte_failover.service.example
│   └── ups_shutdown.service.example
├── docs/                       # All project documentation
│   ├── ARCHITECTURE.md
│   ├── EXECUTIVE_SUMMARY.md
│   ├── FILE_STRUCTURE_DESIGN.md
│   ├── HARDWARE_SOFTWARE.md
│   ├── SCRIPT_INFO.md
│   ├── TECHNICAL_SUMMARY.md
│   └── VALIDATION_REPORT.md
├── .gitignore                  # Git ignore file
└── README.md                   # This file
```

## Setup and Installation

1.  **Prerequisites:**
    *   Raspberry Pi 5 (16GB RAM recommended) with Raspberry Pi OS (or similar Debian-based Linux).
    *   Coral M.2 Dual Edge TPU installed and host drivers configured.
    *   Docker and Docker Compose installed on the Raspberry Pi.
        ```bash
        sudo apt update && sudo apt upgrade -y
        sudo apt install -y docker.io docker-compose-plugin git
        sudo usermod -aG docker $USER
        # Log out and log back in for docker group changes to take effect, or use newgrp docker
        ```
    *   IP Cameras providing RTSP streams.
    *   USB Microphone and Speaker (if using the audio service).

2.  **Clone the Repository:**
    ```bash
    git clone <repository_url> viztron_mvp_refactored
    cd viztron_mvp_refactored
    ```

3.  **Configuration:**
    *   **Copy Example Configuration Files:**
        *   `cp config/frigate.yml.example config/frigate.yml`
        *   `cp config/modules.json.example config/modules.json` (if using CodeProject.AI)
        *   `cp scripts/scorer.env.example scripts/scorer.env`
        *   `cp scripts/audio_service/audio_service.env.example scripts/audio_service/audio_service.env`
    *   **Edit Configuration Files:**
        *   **`config/frigate.yml`**: Configure your MQTT broker details (if different from `mosquitto` default), camera RTSP streams, detector settings (ensure Coral TPU is correctly specified for M.2), recording paths, etc. Pay close attention to `detectors.coral.device` and `ffmpeg.hwaccel_args` for RPi5.
        *   **`config/modules.json`**: Configure enabled AI models for CodeProject.AI if you are using it.
        *   **`scripts/scorer.env`**: Adjust MQTT settings (if not default), scoring thresholds, GPIO pin for alarm, etc.
        *   **`scripts/audio_service/audio_service.env`**: Adjust MQTT settings, audio device indices (if not default), Whisper model size, and paths if necessary.
    *   **Audio Prompts:** Place your actual `.wav` audio prompt files in `scripts/audio_service/prompts/`, replacing the `.example` files (e.g., `hello.wav`, `who_are_you.wav`).
    *   **Docker Compose (`compose/docker-compose.yml`):**
        *   Review device mappings for Frigate (TPU: `/dev/apex_0`, `/dev/apex_1`; hardware video acceleration: `/dev/dri/...`) and the Audio Service (`/dev/snd/...`). These might need adjustment based on your specific RPi5 setup.
        *   Review volume mount paths, especially for Frigate storage (`./frigate_storage/media`). Ensure these directories exist or Docker will create them as root.
        *   This file includes example Dockerfile definitions commented out at the bottom. You will need to create `scripts/Dockerfile.scorer` and `scripts/audio_service/Dockerfile.audio` based on these examples or your specific needs if you are building the images locally.

4.  **Create Dockerfiles (if building locally):**
    *   Create `scripts/Dockerfile.scorer` (see example in `compose/docker-compose.yml` comments).
    *   Create `scripts/audio_service/Dockerfile.audio` (see example in `compose/docker-compose.yml` comments).

5.  **Build and Run Docker Containers:**
    ```bash
    cd compose
    docker compose up --build -d # Use --build the first time or when Dockerfiles change
    ```
    To run without rebuilding (if images are already built):
    ```bash
    docker compose up -d
    ```

## Usage

*   **Frigate Web UI:** `http://<RASPBERRY_PI_IP>:5000`
*   **CodeProject.AI UI (if enabled):** `http://<RASPBERRY_PI_IP>:32168`
*   **View Logs:**
    ```bash
    docker compose logs -f scorer
    docker compose logs -f audio_service
    docker compose logs -f frigate
    # etc.
    ```
*   **Testing GPIO Relay (on host):**
    ```bash
    python3 homebase/gpio_relay.py --pin <YOUR_ALARM_PIN> --test
    ```

## Troubleshooting

*   **Permissions:** Ensure Docker has permissions to access hardware devices (TPUs, audio, GPIO if not using `privileged: true`). Check `dmesg` for hardware-related errors.
*   **MQTT Connection:** Verify all services can connect to the Mosquitto broker. Check service logs for connection errors.
*   **Audio Devices:** Use `arecord -l` and `aplay -l` on the Raspberry Pi host to list available audio input/output devices and their card/device numbers. Update `audio_service.env` or `docker-compose.yml` device mappings accordingly.
*   **Frigate Configuration:** Frigate configuration can be complex. Refer to the official Frigate documentation for detailed guidance on camera setup, object detection, and hardware acceleration.
*   **Python Dependencies:** Ensure all Python dependencies listed in `scripts/audio_service/requirements.txt` (and any needed by `scorer.py` if not using `RPi.GPIO` from base image) are correctly installed in their respective Docker images.

## Contributing

This project is an MVP. Contributions for further enhancements, bug fixes, and documentation improvements are welcome. Please follow standard Git practices (fork, branch, pull request).

## License

Specify your project license here (e.g., MIT, Apache 2.0).

# mvp-test2-manus
