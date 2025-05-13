# gpio_relay.py
# This script provides basic control for a GPIO pin, typically used to activate a relay.
# It can be run directly for testing or imported by other scripts.

import os
import time
import argparse
import logging

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format=\'%(asctime)s - %(levelname)s - %(message)s\

# --- Configuration ---
# Default GPIO pin if not specified by argument or environment variable
DEFAULT_GPIO_PIN = 17

# Attempt to import RPi.GPIO
USE_GPIO = False
GPIO = None
try:
    import RPi.GPIO as GPIO_LIB
    GPIO = GPIO_LIB
    GPIO.setwarnings(False) # Disable GPIO warnings (e.g., channel already in use)
    USE_GPIO = True
    logging.info("RPi.GPIO library loaded successfully.")
except ImportError:
    logging.warning("RPi.GPIO module not found. GPIO functionality will be simulated.")
except Exception as e:
    logging.error(f"Error importing or setting up RPi.GPIO: {e}")

# --- Functions ---
def setup_pin(pin_number):
    """Sets up the specified GPIO pin as an output."""
    if USE_GPIO and GPIO:
        try:
            GPIO.setmode(GPIO.BCM) # Using Broadcom SOC channel numbers
            GPIO.setup(pin_number, GPIO.OUT)
            GPIO.output(pin_number, GPIO.LOW) # Ensure relay is off initially
            logging.info(f"GPIO pin {pin_number} set up as output and initialized to LOW.")
            return True
        except Exception as e:
            logging.error(f"Error setting up GPIO pin {pin_number}: {e}")
            return False
    elif not USE_GPIO:
        logging.info(f"[SIMULATED] GPIO pin {pin_number} set up as output and initialized to LOW.")
        return True
    return False

def set_pin_state(pin_number, state):
    """Sets the specified GPIO pin to the given state (HIGH or LOW)."""
    if not isinstance(state, bool) and state not in [GPIO.HIGH, GPIO.LOW, 1, 0]:
        logging.error(f"Invalid state for pin {pin_number}: {state}. Must be boolean, 0/1, or GPIO.HIGH/LOW.")
        return

    gpio_state_to_set = GPIO.HIGH if state in [True, GPIO.HIGH, 1] else GPIO.LOW
    state_str = "HIGH" if gpio_state_to_set == GPIO.HIGH else "LOW"

    if USE_GPIO and GPIO:
        try:
            GPIO.output(pin_number, gpio_state_to_set)
            logging.info(f"GPIO pin {pin_number} set to {state_str}.")
        except Exception as e:
            logging.error(f"Error setting GPIO pin {pin_number} to {state_str}: {e}")
    elif not USE_GPIO:
        logging.info(f"[SIMULATED] GPIO pin {pin_number} set to {state_str}.")

def toggle_pin(pin_number, delay_seconds=1):
    """Toggles the GPIO pin: HIGH, waits, then LOW."""
    logging.info(f"Toggling GPIO pin {pin_number} ON for {delay_seconds} second(s).")
    set_pin_state(pin_number, True) # Turn ON
    time.sleep(delay_seconds)
    set_pin_state(pin_number, False) # Turn OFF

def cleanup_gpio():
    """Cleans up GPIO resources."""
    if USE_GPIO and GPIO:
        try:
            GPIO.cleanup()
            logging.info("GPIO resources cleaned up.")
        except Exception as e:
            logging.error(f"Error during GPIO cleanup: {e}")
    elif not USE_GPIO:
        logging.info("[SIMULATED] GPIO resources cleaned up.")

# --- Main Execution (for direct script running) ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Control a GPIO relay.")
    parser.add_argument("--pin", type=int, default=int(os.getenv("GPIO_RELAY_PIN", DEFAULT_GPIO_PIN)),
                        help=f"The GPIO pin number (BCM mode). Default: {DEFAULT_GPIO_PIN} or GPIO_RELAY_PIN env var.")
    parser.add_argument("--state", type=str, choices=["on", "off", "toggle"],
                        help="Desired state: 'on' (HIGH), 'off' (LOW), or 'toggle' (on for a delay then off). Required if not testing.")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Delay in seconds for the 'toggle' state. Default: 1.0s")
    parser.add_argument("--test", action="store_true",
                        help="Run a simple toggle test on the specified pin.")

    args = parser.parse_args()

    logging.info(f"gpio_relay.py script initiated with arguments: {args}")

    if not USE_GPIO:
        logging.warning("RPi.GPIO not available. Operations will be simulated.")

    if not setup_pin(args.pin):
        logging.error(f"Failed to set up GPIO pin {args.pin}. Exiting.")
        exit(1)

    try:
        if args.test:
            logging.info(f"Performing toggle test on pin {args.pin} with delay {args.delay}s.")
            toggle_pin(args.pin, args.delay)
        elif args.state == "on":
            set_pin_state(args.pin, True)
        elif args.state == "off":
            set_pin_state(args.pin, False)
        elif args.state == "toggle":
            toggle_pin(args.pin, args.delay)
        else:
            logging.info("No action specified (use --state [on|off|toggle] or --test). Pin has been initialized.")
            parser.print_help()

    except KeyboardInterrupt:
        logging.info("Script interrupted by user.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
    finally:
        # Clean up GPIO only if this script initialized it and is exiting.
        # If imported, the importing script should manage cleanup.
        cleanup_gpio()
        logging.info("gpio_relay.py script finished.")

