# viztron_mvp_refactored Directory Structure Design

## Root Directory: `viztron_mvp_refactored/`

```
viztron_mvp_refactored/
├── compose/
│   └── docker-compose.yml        # Main Docker Compose file orchestrating all services
├── config/
│   ├── frigate.yml.example       # Example configuration for Frigate (cameras, detectors)
│   └── modules.json.example      # Example configuration for CodeProject.AI (AI models)
├── scripts/
│   ├── scorer.py                 # Core threat scoring and decision-making script
│   ├── scorer.env.example        # Example environment variables for scorer.py
│   └── audio_service/
│       ├── audio_service.py      # Script for handling audio inquiries and analysis
│       ├── requirements.txt      # Python dependencies for audio_service.py
│       ├── audio_service.env.example # Example environment variables for audio_service.py
│       └── prompts/              # Directory to store .wav audio prompt files
│           ├── hello.wav.example # Example placeholder for a greeting prompt
│           ├── who_are_you.wav.example # Example placeholder for an identification prompt
│           └── state_reason.wav.example # Example placeholder for a reason-stating prompt
├── homebase/                     # Utility scripts for direct Raspberry Pi hardware interaction
│   ├── gpio_relay.py             # Script for testing/controlling GPIO relays
│   ├── lte_failover.service.example # Example systemd unit file for LTE failover
│   └── ups_shutdown.service.example # Example systemd unit file for UPS graceful shutdown
├── docs/                         # Project documentation files
│   ├── ARCHITECTURE.md           # Detailed system architecture and design choices
│   ├── SCRIPT_INFO.md            # Overview of main scripts, their purpose, and config
│   ├── HARDWARE_SOFTWARE.md      # Confirmation of hardware/software stack and considerations
│   └── VALIDATION_REPORT.md      # Report from the script validation phase
├── .gitignore                    # Specifies intentionally untracked files that Git should ignore
└── README.md                     # Main project README: setup, configuration, usage, troubleshooting
```

## Key Files and Purpose:

*   **`compose/docker-compose.yml`**: Defines and configures the multi-container Docker application (Frigate, CodeProject.AI, Mosquitto, Scorer, Audio Service).
*   **`config/*.example`**: Provides templates for users to create their actual configuration files. Users should copy these and remove the `.example` extension (e.g., `frigate.yml.example` -> `frigate.yml`).
*   **`scripts/scorer.py`**: The central logic for threat assessment.
*   **`scripts/scorer.env.example`**: Template for environment variables needed by `scorer.py`.
*   **`scripts/audio_service/audio_service.py`**: Handles audio interactions (prompts, recording, transcription, basic analysis).
*   **`scripts/audio_service/requirements.txt`**: Lists Python packages required by `audio_service.py` (e.g., `pyaudio`, `openai-whisper`, `paho-mqtt`).
*   **`scripts/audio_service/audio_service.env.example`**: Template for environment variables for `audio_service.py`.
*   **`scripts/audio_service/prompts/*.wav.example`**: Placeholder files indicating where users should place their actual `.wav` audio prompts.
*   **`homebase/`**: Contains scripts for direct hardware interaction on the Raspberry Pi, intended to be run on the host or with specific Docker privileges.
    *   `gpio_relay.py`: Utility for testing GPIO pins.
    *   `*.service.example`: Example systemd unit files for host-level services.
*   **`docs/`**: Contains detailed documentation generated during the project analysis and development.
*   **`.gitignore`**: Standard file to exclude common temporary files, logs, Python virtual environments, and Docker build artifacts from Git.
*   **`README.md`**: The primary entry point for users. It will explain the project, how to set it up (clone, configure, run Docker Compose), basic usage, and troubleshooting tips.

## Next Steps for Implementation:

1.  Create the `docs/` directory and move existing markdown reports into it, renaming them as specified (e.g., `architecture_review.md` to `docs/ARCHITECTURE.md`).
2.  Create the example configuration files (`frigate.yml.example`, `modules.json.example`, `scorer.env.example`, `audio_service.env.example`).
3.  Create the `scripts/audio_service/requirements.txt` file.
4.  Create placeholder `.wav.example` files in `scripts/audio_service/prompts/`.
5.  Create example systemd service files in `homebase/`.
6.  Draft the `docker-compose.yml` file based on the refined architecture and script locations.
7.  Create a comprehensive `.gitignore` file.
8.  Draft the main `README.md` file.

This structure aims for clarity, ease of use, and good practice for a GitHub repository.
