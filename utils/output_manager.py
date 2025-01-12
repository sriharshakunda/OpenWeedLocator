from threading import Thread, Event, Condition, Lock
from utils.vis_manager import RelayVis
from utils.error_manager import OWLAlreadyRunningError
from utils.log_manager import LogManager
from enum import Enum
from collections import deque
import subprocess
import shutil
import time
import logging
import platform

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

def get_platform_config():
    """Determine platform and return testing status and GPIO error type."""
    if is_jetson_nano():
        try:
            import Jetson.GPIO as GPIO
            return False, None  # No specific error for Jetson.GPIO
        except ImportError as e:
            logger.error("Failed to import Jetson.GPIO: {}".format(e))
            return True, e
    else:
        # Unsupported platform (e.g., Windows)
        is_windows = platform.system() == "Windows"
        system_name = "Windows" if is_windows else "unrecognized"
        logger.warning(
            "The system is running on a {} platform. GPIO disabled. Test mode active.".format(system_name)
        )
        return True, None

testing, gpioERROR = get_platform_config()

# Import GPIO components only if needed
if not testing:
    import Jetson.GPIO as GPIO

# Test classes to run the analysis on a desktop computer if a "win32" platform is detected
class TestRelay:
    def __init__(self, relay_number, verbose=False):
        self.relay_number = relay_number
        self.verbose = verbose

    def on(self):
        if self.verbose:
            print("[TEST] Relay {} ON".format(self.relay_number))

    def off(self):
        if self.verbose:
            print("[TEST] Relay {} OFF".format(self.relay_number))

class TestBuzzer:
    def beep(self, on_time, off_time, n=1, verbose=False):
        for i in range(n):
            if verbose:
                print('BEEP')

class TestLED:
    def __init__(self, pin):
        self.pin = pin

    def blink(self, on_time=0.1, off_time=0.1, n=1, verbose=False, background=True):
        if n is None:
            n = 1

        for i in range(n):
            if verbose:
                print('BLINK {}'.format(self.pin))

    def on(self):
        print('LED {} ON'.format(self.pin))

    def off(self):
        print('LED {} OFF'.format(self.pin))


class BaseStatusIndicator:
    def __init__(self, save_directory, no_save=False):
        self.logger = LogManager.get_logger(__name__)

        self.save_directory = save_directory
        self.no_save = no_save
        self.testing = True if testing else False
        self.storage_used = None
        self.storage_total = None
        self.update_event = Event()
        self.running = True
        self.thread = None
        self.DRIVE_FULL = False

        self.error_code = None
        self.flashing_thread = None
        self._set_led_trigger("ACT", "none")
        self._set_led_trigger("PWR", "none")

    def start_storage_indicator(self):
        self.thread = Thread(target=self.run_update)
        self.thread.start()

    def run_update(self):
        while self.running:
            self.update()
            self.update_event.wait(10.5)
            self.update_event.clear()

    def update(self):
        if self.save_directory is not None:
            self.storage_total, self.storage_used, _ = shutil.disk_usage(self.save_directory)
            percent_full = (self.storage_used / self.storage_total)
            self._update_storage_indicator(percent_full)

        elif self.no_save:
            pass

        else:
            self.error(6)

    def error(self, error_code):
        self.error_code = error_code
        if self.flashing_thread is None or not self.flashing_thread.is_alive():
            self.flashing_thread = Thread(target=self._flash_error_code)
            self.flashing_thread.start()

    def _flash_error_code(self):
        while self.running:
            for _ in range(self.error_code):
                self._blink_leds()
                time.sleep(0.2)  # Interval between flashes
            time.sleep(2)  # Pause after each sequence

    def _blink_leds(self):
        self._set_led_state("ACT", 1)
        self._set_led_state("PWR", 1)
        time.sleep(0.2)
        self._set_led_state("ACT", 0)
        self._set_led_state("PWR", 0)

    def _set_led_state(self, led, state):
        if not self.testing:
            LED_PATHS = {
                "ACT": "/sys/class/leds/ACT/brightness",
                "PWR": "/sys/class/leds/PWR/brightness"
            }
            try:
                subprocess.run(
                    ['sudo', 'sh', '-c', 'echo {} > {}'.format(1 if state else 0, LED_PATHS[led])],
                    check=True
                )
            except subprocess.CalledProcessError as e:
                self.logger.error("Error: Could not set {} LED. {}".format(led, e), exc_info=True)

    def _set_led_trigger(self, led, trigger):
        if not self.testing:
            LED_TRIGGER_PATHS = {
                "ACT": "/sys/class/leds/ACT/trigger",
                "PWR": "/sys/class/leds/PWR/trigger"
            }
            try:
                subprocess.run(
                    ['sudo', 'sh', '-c', 'echo {} > {}'.format(trigger, LED_TRIGGER_PATHS[led])],
                    check=True
                )
            except subprocess.CalledProcessError as e:
                self.logger.error("Error: Could not set {} trigger to {}.".format(led, trigger), exc_info=True)

    def _update_storage_indicator(self, percent_full):
        self.logger.warning("Called _update_storage_indicator() but it's not implemented.")
        raise NotImplementedError("This method should be implemented by subclasses")

    def stop(self):
        """Stop all threads and ensure resources are cleaned up."""
        self.running = False
        self.update_event.set()  # Wake up storage indicator thread

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)  # Ensure thread stops

        if self.flashing_thread and self.flashing_thread.is_alive():
            self.flashing_thread.join(timeout=1)  # Ensure flashing thread stops

        self._cleanup_leds()
        logger.info("[INFO] StatusIndicator stopped.")

    def _cleanup_leds(self):
        """Turn off LEDs and reset their states."""
        try:
            self._set_led_state("ACT", 0)
            self._set_led_state("PWR", 0)
        except Exception as e:
            logger.error("Failed to clean up LEDs: {}".format(e))


class HeadlessStatusIndicator(BaseStatusIndicator):
    def __init__(self, save_directory=None, no_save=False):
        super().__init__(save_directory, no_save)

    def _update_storage_indicator(self, percent_full):
        if percent_full >= 0.90:
            self.DRIVE_FULL = True


class UteStatusIndicator(BaseStatusIndicator):
    def __init__(self, save_directory, record_led_pin=38, storage_led_pin=40):
        super().__init__(save_directory)
        LED_class = TestLED if testing else lambda pin: GPIO.setup(pin, GPIO.OUT)
        self.record_LED = LED_class(record_led_pin)
        self.storage_LED = LED_class(storage_led_pin)

    def _update_storage_indicator(self, percent_full):
        if percent_full >= 0.90:
            self.DRIVE_FULL = True
            self.storage_LED.on()
            self.record_LED.off()
        elif percent_full >= 0.85:
            self.storage_LED.blink(on_time=0.2, off_time=0.2, n=None, background=True)
        elif percent_full >= 0.80:
            self.storage_LED.blink(on_time=0.5, off_time=0.5, n=None, background=True)
        elif percent_full >= 0.75:
            self.storage_LED.blink(on_time=0.5, off_time=1.5, n=None, background=True)
        elif percent_full >= 0.5:
            self.storage_LED.blink(on_time=0.5, off_time=3.0, n=None, background=True)
        else:
            self.storage_LED.blink(on_time=0.5, off_time=4.5, n=None, background=True)

    def setup_success(self):
        self.storage_LED.blink(on_time=0.1, off_time=0.2, n=3)
        self.record_LED.blink(on_time=0.1, off_time=0.2, n=3)

    def image_write_indicator(self):
        self.record_LED.blink(on_time=0.1, n=1, background=True)

    def alert_flash(self):
        self.storage_LED.blink(on_time=0.5, off_time=0.5, n=None, background=True)
        self.record_LED.blink(on_time=0.5, off_time=0.5, n=None, background=True)

    def error(self, error_code):
        self.error_code = error_code
        if self.flashing_thread is None or not self.flashing_thread.is_alive():
            self.flashing_thread = Thread(target=self._flash_error_code)
            self.flashing_thread.start()

    def _flash_error_code(self):
        while self.running:
            for _ in range(self.error_code):
                self._blink_leds()
                self.storage_LED.blink(on_time=0.2, n=1, background=False)  # Flash storage LED
                self.record_LED.blink(on_time=0.2, n=1, background=False)  # Flash record LED
                time.sleep(0.2)  # Interval between flashes
            time.sleep(2)  # Pause after each sequence

    def stop(self):
        super().stop()
        if self.flashing_thread and self.flashing_thread.is_alive():
            self.flashing_thread.join()
        self.storage_LED.off()
        self.record_LED.off()


class AdvancedIndicatorState(Enum):
    IDLE = 0
    RECORDING = 1
    DETECTING = 2
    NOTIFICATION = 3
    RECORDING_AND_DETECTING = 4
    ERROR = 5


class AdvancedStatusIndicator(BaseStatusIndicator):
    def __init__(self, save_directory, status_led_pin=37):
        super().__init__(save_directory)
        LED_class = TestLED if testing else lambda pin: GPIO.setup(pin, GPIO.OUT)
        self.led = LED_class(status_led_pin)
        self.state = AdvancedIndicatorState.IDLE
        self.error_queue = deque()
        self.state_lock = Lock()
        self.weed_detection_enabled = False
        self.image_recording_enabled = False
        self.flashing_thread = None

    def _update_storage_indicator(self, percent_full):
        if percent_full >= 0.90:
            self.DRIVE_FULL = True
            self.error(1)  # Use error code 1 for drive full

    def setup_success(self):
        self.led.blink(on_time=0.1, off_time=0.1, n=2)

    def _update_state(self):
        if self.state != AdvancedIndicatorState.ERROR:
            if self.weed_detection_enabled and self.image_recording_enabled:
                self.state = AdvancedIndicatorState.RECORDING_AND_DETECTING
            elif self.weed_detection_enabled:
                self.state = AdvancedIndicatorState.DETECTING
            elif self.image_recording_enabled:
                self.state = AdvancedIndicatorState.RECORDING
            else:
                self.state = AdvancedIndicatorState.IDLE

    def enable_weed_detection(self):
        with self.state_lock:
            self.weed_detection_enabled = True
            self._update_state()

    def disable_weed_detection(self):
        with self.state_lock:
            self.weed_detection_enabled = False
            self._update_state()

    def enable_image_recording(self):
        with self.state_lock:
            self.image_recording_enabled = True
            self._update_state()

    def disable_image_recording(self):
        with self.state_lock:
            self.image_recording_enabled = False
            self._update_state()

    def image_write_indicator(self):
        with self.state_lock:
            if self.state not in [AdvancedIndicatorState.ERROR, AdvancedIndicatorState.DETECTING,
                                  AdvancedIndicatorState.RECORDING_AND_DETECTING]:
                try:
                    self.led.blink(on_time=0.1, off_time=0.1, n=1, background=True)
                except KeyboardInterrupt:
                    logger.info("[INFO] KeyboardInterrupt received during image_write_indicator. Turning off LED.")
                    self.led.off()
                    raise
                except Exception as e:
                    logger.error("Error in image_write_indicator: {}".format(e), exc_info=True)

    def weed_detect_indicator(self):
        with self.state_lock:
            if self.state in [AdvancedIndicatorState.DETECTING, AdvancedIndicatorState.RECORDING_AND_DETECTING]:
                try:
                    self.led.blink(on_time=0.05, off_time=0.05, n=1, background=True)
                except KeyboardInterrupt:
                    logger.info("[INFO] KeyboardInterrupt received during weed_detect_indicator. Turning off LED.")
                    self.led.off()
                    raise
                except Exception as e:
                    logger.error("Error in weed_detect_indicator: {}".format(e), exc_info=True)

    def generic_notification(self):
        try:
            with self.state_lock:
                init_state = self.state
                self.state = AdvancedIndicatorState.NOTIFICATION
                self.led.off()  # Reset LED state before notification

                self.led.blink(on_time=0.1, off_time=0.1, n=2, background=False)
                self.state = init_state
        except KeyboardInterrupt:
            logger.info("[INFO] KeyboardInterrupt received during generic_notification. Turning off LED.")
            self.led.off()
            raise
        except Exception as e:
            logger.error("Error in generic_notification: {}".format(e), exc_info=True)

    def error(self, error_code):
        self.error_code = error_code
        with self.state_lock:
            self.state = AdvancedIndicatorState.ERROR
        if self.flashing_thread is None or not self.flashing_thread.is_alive():
            self.flashing_thread = Thread(target=self._flash_error_code)
            self.flashing_thread.start()

    def _flash_error_code(self):
        try:
            while self.running:
                for _ in range(self.error_code):
                    self._blink_leds()
                    time.sleep(0.2)
                time.sleep(2)
        except KeyboardInterrupt:
            logger.info("[INFO] KeyboardInterrupt received in _flash_error_code. Exiting.")
        except Exception as e:
            logger.error("Error in _flash_error_code: {}".format(e), exc_info=True)
        finally:
            self._cleanup_leds()

    def stop(self):
        super().stop()
        if self.flashing_thread and self.flashing_thread.is_alive():
            self.flashing_thread.join()
        self.led.off()


# Control class for the relay board
class RelayControl:
    def __init__(self, relay_dict):
        self.logger = LogManager.get_logger(__name__)

        self.testing = True if testing else False
        self.relay_dict = relay_dict
        self.on = False

        # Used to toggle activation of GPIO pins for LEDs
        self.field_data_recording = False

        if not self.testing:
            try:
                self.buzzer = GPIO.setup(7, GPIO.OUT)  # Buzzer on pin 7
            except Exception as e:
                if isinstance(e, gpioERROR) and 'GPIO busy' in str(e):
                    raise OWLAlreadyRunningError("OWL instance may already be running.") from e
                else:
                    raise

            for relay, board_pin in self.relay_dict.items():
                self.relay_dict[relay] = GPIO.setup(board_pin, GPIO.OUT)

        else:
            self.buzzer = TestBuzzer()
            for relay, board_pin in self.relay_dict.items():
                self.relay_dict[relay] = TestRelay(board_pin)

    def relay_on(self, relay_number, verbose=True):
        relay = self.relay_dict[relay_number]
        GPIO.output(relay, GPIO.HIGH)

        if verbose:
            print("Relay {} ON".format(relay_number))

    def relay_off(self, relay_number, verbose=True):
        relay = self.relay_dict[relay_number]
        GPIO.output(relay, GPIO.LOW)

        if verbose:
            print("Relay {} OFF".format(relay_number))

    def beep(self, duration=0.2, repeats=2):
        for _ in range(repeats):