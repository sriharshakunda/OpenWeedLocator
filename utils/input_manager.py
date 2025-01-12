import time
import configparser
import subprocess
import cv2
import logging
import Jetson.GPIO as GPIO

logger = logging.getLogger(__name__)

def is_jetson_nano() -> bool:
    """
    Check if the system is running on a Jetson Nano or other Jetson device.
    Relies on the presence of Jetson-specific hardware or files.
    """
    try:
        with open("/proc/device-tree/model", "r") as f:
            model = f.read().lower()
            return "jetson" in model
    except FileNotFoundError:
        return False

# Initialize GPIO mode
GPIO.setmode(GPIO.BOARD)  # Use BOARD pin numbering (or GPIO.BCM for BCM numbering)

class UteController:
    def __init__(self, detection_state,
                 sample_state,
                 stop_flag,
                 owl_instance,
                 status_indicator,
                 switch_purpose='recording',
                 switch_board_pin=37,  # Use BOARD pin number
                 bounce_time=1.0):

        self.switch_pin = switch_board_pin
        GPIO.setup(self.switch_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Set up as input with pull-up
        self.switch_purpose = switch_purpose

        self.detection_state = detection_state
        self.sample_state = sample_state

        self.owl = owl_instance
        self.status_indicator = status_indicator
        self.status_indicator.start_storage_indicator()

        self.stop_flag = stop_flag

        # Initialize state based on initial switch position
        self.update_state()

    def update_state(self):
        is_active = GPIO.input(self.switch_pin) == GPIO.LOW  # Active low (pressed = LOW)

        if self.switch_purpose == 'detection':
            with self.detection_state.get_lock():
                self.detection_state.value = is_active
            self.owl.disable_detection = not is_active
            if is_active:
                self.status_indicator.enable_weed_detection()
            else:
                self.status_indicator.disable_weed_detection()

        elif self.switch_purpose == 'recording':
            with self.sample_state.get_lock():
                self.sample_state.value = is_active
            self.owl.sample_images = is_active
            if is_active:
                self.status_indicator.enable_image_recording()
            else:
                self.status_indicator.disable_image_recording()

    def toggle_state(self):
        self.update_state()

    def weed_detect_indicator(self):
        self.status_indicator.weed_detect_indicator()

    def image_write_indicator(self):
        self.status_indicator.image_write_indicator()

    def run(self):
        try:
            while not self.stop_flag.value:
                self.update_state()  # Continuously check the switch state
                time.sleep(0.1)  # Sleep to reduce CPU usage
        except KeyboardInterrupt:
            logger.info("[INFO] KeyboardInterrupt received in controller run loop. Exiting.")
            self.stop()  # Ensure the stop flag is set
        except Exception as e:
            logger.error(f"Error in controller run loop: {e}", exc_info=True)

    def stop(self):
        with self.stop_flag.get_lock():
            self.stop_flag.value = True
        GPIO.cleanup(self.switch_pin)  # Clean up the GPIO pin


class AdvancedController:
    def __init__(self, recording_state,
                 sensitivity_state,
                 detection_mode_state,
                 stop_flag,
                 owl_instance,
                 status_indicator,
                 low_sensitivity_config,
                 high_sensitivity_config,
                 detection_mode_pin_down=35,  # Use BOARD pin number
                 detection_mode_pin_up=36,    # Use BOARD pin number
                 recording_pin=38,            # Use BOARD pin number
                 sensitivity_pin=40,          # Use BOARD pin number
                 bounce_time=1.0):

        # Set up GPIO pins
        self.recording_pin = recording_pin
        self.sensitivity_pin = sensitivity_pin
        self.detection_mode_pin_up = detection_mode_pin_up
        self.detection_mode_pin_down = detection_mode_pin_down

        GPIO.setup(self.recording_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.sensitivity_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.detection_mode_pin_up, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.detection_mode_pin_down, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        self.recording_state = recording_state
        self.sensitivity_state = sensitivity_state
        self.detection_mode_state = detection_mode_state

        self.stop_flag = stop_flag

        # Set up instances for owl and status
        self.owl = owl_instance
        self.status_indicator = status_indicator
        self.status_indicator.start_storage_indicator()

        self.low_sensitivity_settings = self._read_config(low_sensitivity_config)
        self.high_sensitivity_settings = self._read_config(high_sensitivity_config)

        # Initialize states based on initial switch positions
        self.update_state()

    def update_state(self):
        try:
            self.update_recording_state()
            self.update_sensitivity_state()
            self.update_detection_mode_state()
        except KeyboardInterrupt:
            logger.info("[INFO] KeyboardInterrupt received in update_state. Exiting.")
            raise  # Propagate to hoot()
        except Exception as e:
            logger.error(f"Error in update_state: {e}", exc_info=True)

    def update_recording_state(self):
        is_active = GPIO.input(self.recording_pin) == GPIO.LOW  # Active low (pressed = LOW)
        with self.recording_state.get_lock():
            self.recording_state.value = is_active
        if is_active:
            self.status_indicator.enable_image_recording()
            self.owl.sample_images = True
        else:
            self.status_indicator.disable_image_recording()
            self.owl.sample_images = False

    def update_sensitivity_state(self):
        is_active = GPIO.input(self.sensitivity_pin) == GPIO.LOW  # Active low (pressed = LOW)
        with self.sensitivity_state.get_lock():
            self.sensitivity_state.value = is_active
        self.update_sensitivity_settings()

    def update_sensitivity_settings(self):
        settings = self.low_sensitivity_settings if self.sensitivity_state.value else self.high_sensitivity_settings

        # Update Owl instance settings
        self.owl.exg_min = settings['exg_min']
        self.owl.exg_max = settings['exg_max']
        self.owl.hue_min = settings['hue_min']
        self.owl.hue_max = settings['hue_max']
        self.owl.saturation_min = settings['saturation_min']
        self.owl.saturation_max = settings['saturation_max']
        self.owl.brightness_min = settings['brightness_min']
        self.owl.brightness_max = settings['brightness_max']

        # Update trackbars if show_display is True
        if self.owl.show_display:
            cv2.setTrackbarPos("ExG-Min", self.owl.window_name, self.owl.exg_min)
            cv2.setTrackbarPos("ExG-Max", self.owl.window_name, self.owl.exg_max)
            cv2.setTrackbarPos("Hue-Min", self.owl.window_name, self.owl.hue_min)
            cv2.setTrackbarPos("Hue-Max", self.owl.window_name, self.owl.hue_max)
            cv2.setTrackbarPos("Sat-Min", self.owl.window_name, self.owl.saturation_min)
            cv2.setTrackbarPos("Sat-Max", self.owl.window_name, self.owl.saturation_max)
            cv2.setTrackbarPos("Bright-Min", self.owl.window_name, self.owl.brightness_min)
            cv2.setTrackbarPos("Bright-Max", self.owl.window_name, self.owl.brightness_max)

    def set_detection_mode(self, mode):
        try:
            with self.detection_mode_state.get_lock():
                self.detection_mode_state.value = mode

            self.status_indicator.generic_notification()

            if mode == 0:  # Detection on
                self.status_indicator.enable_weed_detection()
                self.owl.disable_detection = False
            elif mode == 2:  # All solenoids on
                self.status_indicator.disable_weed_detection()
                self.owl.relay_controller.relay.all_on()
                self.owl.disable_detection = True
            else:  # Off or any unexpected value
                self.status_indicator.disable_weed_detection()
                self.owl.relay_controller.relay.all_off()
                self.owl.disable_detection = True
        except KeyboardInterrupt:
            logger.info("[INFO] KeyboardInterrupt received in set_detection_mode. Exiting.")
            raise
        except Exception as e:
            logger.error(f"Error in set_detection_mode: {e}", exc_info=True)

    def update_detection_mode_state(self):
        if GPIO.input(self.detection_mode_pin_up) == GPIO.LOW:
            self.set_detection_mode(2)  # All solenoids on
        elif GPIO.input(self.detection_mode_pin_down) == GPIO.LOW:
            self.set_detection_mode(0)  # Detection on
        else:
            self.set_detection_mode(1)  # Off

    def weed_detect_indicator(self):
        self.status_indicator.weed_detect_indicator()

    def image_write_indicator(self):
        self.status_indicator.image_write_indicator()

    def run(self):
        try:
            while not self.stop_flag.value:
                self.update_state()  # Continuously check the switch states
                time.sleep(0.1)  # Sleep to reduce CPU usage
        except KeyboardInterrupt:
            logger.info("[INFO] KeyboardInterrupt received in controller run loop. Exiting.")
            self.stop()  # Ensure the stop flag is set
        except Exception as e:
            logger.error(f"Error in controller run loop: {e}", exc_info=True)

    def stop(self):
        with self.stop_flag.get_lock():
            self.stop_flag.value = True
        GPIO.cleanup([self.recording_pin, self.sensitivity_pin, self.detection_mode_pin_up, self.detection_mode_pin_down])

    def _read_config(self, config_file):
        config = configparser.ConfigParser()
        config.read(config_file)
        return {
            'exg_min': config.getint('GreenOnBrown', 'exg_min'),
            'exg_max': config.getint('GreenOnBrown', 'exg_max'),
            'hue_min': config.getint('GreenOnBrown', 'hue_min'),
            'hue_max': config.getint('GreenOnBrown', 'hue_max'),
            'saturation_min': config.getint('GreenOnBrown', 'saturation_min'),
            'saturation_max': config.getint('GreenOnBrown', 'saturation_max'),
            'brightness_min': config.getint('GreenOnBrown', 'brightness_min'),
            'brightness_max': config.getint('GreenOnBrown', 'brightness_max')
        }


def get_jetson_version() -> str:
    """
    Identify the specific Jetson device by reading the hardware model.
    Returns a string indicating the Jetson device (e.g., 'jetson-nano', 'jetson-xavier').
    """
    try:
        with open("/proc/device-tree/model", "r") as f:
            model = f.read().lower()
            if "nano" in model:
                return "jetson-nano"
            elif "xavier" in model:
                return "jetson-xavier"
            elif "orin" in model:
                return "jetson-orin"
            elif "agx" in model:
                return "jetson-agx"
            else:
                return "jetson-unknown"
    except FileNotFoundError:
        return "non-jetson"