# Hardware and Software Stack Confirmation for RPi5 & Coral M.2 Dual Edge TPU

This document confirms the suitability of the proposed software stack for the Raspberry Pi 5 with an M.2 Accelerator (Dual Edge TPU) and outlines necessary configurations and potential refinements.

## 1. Hardware Compatibility

*   **Raspberry Pi 5 (16GB):** The RPi5 is a capable platform for this project. The 16GB RAM is ample for running the Dockerized services.
*   **M.2 Accelerator with Dual Edge TPU:** This is a key component for AI processing.
    *   **Frigate:** Will be the primary consumer of the Edge TPUs for object detection. It supports M.2 TPUs.
    *   **CodeProject.AI:** Can also leverage TPUs if models are compatible and configured, but Frigate is the main focus for TPU acceleration in the current design.

## 2. Software Stack Confirmation & Refinements

### 2.1. Core Operating System & Containerization

*   **OS:** Raspberry Pi OS (or a similar Debian-based Linux distribution) is assumed for the RPi5.
*   **Docker & Docker Compose:** This is an appropriate and efficient way to manage the various services. The provided `docker-compose.yml` forms a good base.

### 2.2. Key Services and Configurations

*   **Frigate (`blakeblackshear/frigate:stable`):
    *   **TPU Access (Crucial for M.2 Dual TPU):** The `docker-compose.yml` needs adjustment for M.2 TPUs. Instead of `devices: - /dev/bus/usb`, it will require PCIe device passthrough. Typically, M.2 Coral TPUs appear as `/dev/apex_0`, `/dev/apex_1`, etc. The `devices` section for Frigate should be updated to include these:
        ```yaml
        devices:
          - /dev/apex_0:/dev/apex_0
          - /dev/apex_1:/dev/apex_1 # If using both TPUs in Frigate
          # Potentially other necessary devices like /dev/dri for video hardware acceleration
        ```
        The `privileged: true` flag for Frigate is often necessary for full hardware access.
    *   **`frigate.yml` Configuration:**
        *   The `detectors` section should correctly reference the Edge TPU. For M.2, `type: edgetpu` is standard. If using multiple TPUs within Frigate, its documentation should be consulted for specific configuration (e.g., assigning detectors to specific TPU devices if needed, or if Frigate automatically utilizes all passed-through TPUs).
        *   The `ffmpeg` settings and camera inputs are standard.
        *   The `detect.fps` of 5 is a reasonable starting point for resource management on an RPi5, even with TPUs, balancing detection performance with system load. The camera itself can stream at a higher FPS for recording.

*   **CodeProject.AI (`codeproject/ai-server:latest`):
    *   This service is generally compatible. If it needs to use the Edge TPU as well (and Frigate isn't using both), similar device passthrough might be needed for its container.

*   **Mosquitto (`eclipse-mosquitto`):
    *   Standard MQTT broker, lightweight and suitable. No specific RPi5/TPU issues.

*   **Scorer Service (`python:3.10-slim` with `scorer.py`):
    *   **GPIO Access:** The script uses `RPi.GPIO`. The container needs:
        1.  The `RPi.GPIO` Python library installed. This should be added to a `requirements.txt` for the scorer service and installed during its setup (e.g., in the `command` or a dedicated Dockerfile).
        2.  Access to GPIO hardware. This can be achieved by running the container with `privileged: true` or by mapping specific devices like `/dev/gpiomem`:
            ```yaml
            scorer:
              # ... other settings
              privileged: true # Simplest way, or map /dev/gpiomem
            ```
    *   The `env_file` for configuration is good practice.
    *   Mounting `gpio_relay.py` is a good way to share the utility.

*   **Audio Service (`python:3.10-slim` with `audio_service.py`):
    *   **Dependencies:** `pyaudio` requires system libraries like `libportaudio2` and `portaudio19-dev`. These must be installed in the Docker image. The `command` in `docker-compose.yml` should be updated:
        ```yaml
        command: >
          sh -c "apt-get update && apt-get install -y libportaudio2 portaudio19-dev && \
                   pip install --no-cache-dir -r requirements.txt && \
                   python audio_service.py"
        ```
        (Note: Add `apt-get clean` and remove `/var/lib/apt/lists/*` to keep the image smaller if building a custom Dockerfile).
    *   **Audio Hardware Access:** The `devices: ["hw:1,0"]` mapping is correct in principle but the exact device ID (`hw:1,0`) can vary. Making this configurable via an environment variable in `docker-compose.yml` is recommended for flexibility.
    *   **Whisper Model:** `whisper-tiny-int8` is appropriate for the RPi5 in terms of resource usage.

*   **`homebase/` Utilities & Systemd Services:
    *   `gpio_relay.py`: Same GPIO considerations as `scorer.py` if run directly on the host, or if containerized.
    *   `lte_failover.service` & `ups_shutdown.service`: These are host-level systemd services and are configured correctly for that context. They interact directly with the RPi5 OS and hardware.

## 3. General Recommendations

*   **Python Versions:** Using `python:3.10-slim` as a base for the Python services is a good choice for a balance of features and image size.
*   **Resource Monitoring:** Once deployed, monitor CPU, memory, and TPU utilization to ensure the RPi5 is handling the load efficiently and to identify any bottlenecks.
*   **AWS Greengrass:** If Greengrass integration is a firm requirement for the MVP, its impact on the software stack (e.g., choice of MQTT broker, deployment strategy for components) needs to be factored in. The current stack is host-managed Docker; Greengrass would introduce its own lifecycle and communication patterns.

## Conclusion

The proposed software stack is largely compatible with the Raspberry Pi 5 and M.2 Dual Edge TPU hardware. Key areas for attention are:

1.  **Correct M.2 TPU device passthrough** to the Frigate Docker container.
2.  Ensuring **`RPi.GPIO` is installed and accessible** within the `scorer` container.
3.  Installing **`pyaudio` system dependencies** within the `audio_service` container.

Addressing these points will ensure the hardware is utilized effectively by the software components.
