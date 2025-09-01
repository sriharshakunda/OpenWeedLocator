import cv2
import time
import platform
import numpy as np
import subprocess

from threading import Thread, Event, Condition, Lock
from utils.log_manager import LogManager

# Try to import ArducamUtils for Arducam camera support
try:
    from .arducam_utils import ArducamUtils
    ARDUCAM_AVAILABLE = True
except ImportError as e:
    ARDUCAM_AVAILABLE = False
    print(f"ArducamUtils not available: {e}")

# Jetson-only setup - Pi camera support removed

# Enhanced Jetson platform detection
def is_jetson():
    """Check if running on Jetson platform with detailed detection"""
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().strip().lower()
            if 'jetson' in model:
                print(f"Detected Jetson platform: {model}")
                return True
    except (FileNotFoundError, IOError):
        pass
    
    # Additional check for Jetson via tegra
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read().lower()
            if 'tegra' in cpuinfo:
                print("Detected Tegra platform (likely Jetson)")
                return True
    except (FileNotFoundError, IOError):
        pass
    
    print("Not running on Jetson platform")
    return False

JETSON_PLATFORM = is_jetson()

# class to support webcams
class WebcamStream:
    def __init__(self, src=0):
        self.logger = LogManager.get_logger(__name__)
        self.name = "WebcamStream"
        self.logger.info(f'Camera type: {self.name}')
        self.stream = cv2.VideoCapture(src)

        self.frame_width = self.stream.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.frame_height = self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT)

        # Check if the stream opened successfully
        if not self.stream.isOpened():
            self.stream.release()
            self.logger.error(f'Unable to open video source: {src}')
            raise ValueError("Unable to open video source:", src)

        # read the first frame from the stream
        self.grabbed, self.frame = self.stream.read()
        if not self.grabbed:
            self.stream.release()
            self.logger.error(f'Unable to read from video source: {src}')
            raise ValueError("Unable to read from video source:", src)

        # initialize the thread name, stop event, and the thread itself
        self.stop_event = Event()
        self.thread = Thread(target=self.update, name=self.name, args=())
        self.thread.daemon = True

    def start(self):
        self.thread.start()
        return self

    def update(self):
        # keep looping infinitely until the thread is stopped
        try:
            while not self.stop_event.is_set():
                # Read the next frame from the stream
                self.grabbed, self.frame = self.stream.read()

                # If not grabbed, end of the stream has been reached.
                if not self.grabbed:
                    self.stop_event.set()  # Ensure the loop stops if no frame is grabbed
        except Exception as e:
            self.logger.error(f"Exception in WebcamStream update loop: {e}", exc_info=True)
        finally:
            # Clean up resources after loop is done
            self.stream.release()

    def read(self):
        # return the frame most recently read
        return self.frame

    def stop(self):
        self.stop_event.set()
        self.thread.join()


class JetsonCSIStream:
    def __init__(self, sensor_id=0, resolution=(416, 320), framerate=30, **kwargs):
        self.logger = LogManager.get_logger(__name__)
        self.name = "JetsonCSIStream"
        self.logger.info(f'Camera type: {self.name}')
        
        self.sensor_id = sensor_id
        self.frame_width = resolution[0]
        self.frame_height = resolution[1]
        self.framerate = framerate
        
        # Create GStreamer pipeline for Jetson CSI camera
        gst_pipeline = (
            f"nvarguscamerasrc sensor-id={sensor_id} ! "
            f"video/x-raw(memory:NVMM), width={self.frame_width}, height={self.frame_height}, "
            f"format=NV12, framerate={framerate}/1 ! "
            f"nvvidconv flip-method=0 ! "
            f"video/x-raw, width={self.frame_width}, height={self.frame_height}, format=BGRx ! "
            f"videoconvert ! "
            f"video/x-raw, format=BGR ! appsink drop=1"
        )
        
        self.logger.info(f"Using GStreamer pipeline: {gst_pipeline}")
        
        # Initialize camera with GStreamer pipeline
        self.stream = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
        
        # Check if the stream opened successfully
        if not self.stream.isOpened():
            self.stream.release()
            self.logger.error(f'Unable to open Jetson CSI camera {sensor_id}')
            raise ValueError(f"Unable to open Jetson CSI camera {sensor_id}")

        # read the first frame from the stream
        self.grabbed, self.frame = self.stream.read()
        if not self.grabbed:
            self.stream.release()
            self.logger.error(f'Unable to read from Jetson CSI camera {sensor_id}')
            raise ValueError(f"Unable to read from Jetson CSI camera {sensor_id}")

        # initialize the thread name, stop event, and the thread itself
        self.stop_event = Event()
        self.thread = Thread(target=self.update, name=self.name, args=())
        self.thread.daemon = True

    def start(self):
        self.thread.start()
        return self

    def update(self):
        # keep looping infinitely until the thread is stopped
        try:
            while not self.stop_event.is_set():
                # Read the next frame from the stream
                self.grabbed, self.frame = self.stream.read()

                # If not grabbed, end of the stream has been reached.
                if not self.grabbed:
                    self.stop_event.set()  # Ensure the loop stops if no frame is grabbed
        except Exception as e:
            self.logger.error(f"Exception in JetsonCSIStream update loop: {e}", exc_info=True)
        finally:
            # Clean up resources after loop is done
            self.stream.release()

    def read(self):
        # return the frame most recently read
        return self.frame

    def stop(self):
        self.stop_event.set()
        self.thread.join()



class ArducamStream:
    def __init__(self, src=0, resolution=(416, 320), exposure=4000, **kwargs):
        import time
        import subprocess
        from threading import Thread, Event
        from utils.log_manager import LogManager
        self.logger = LogManager.get_logger(__name__)
        self.name = "ArducamStream"
        self.logger.info(f'Camera type: {self.name}')

        # Store src for v4l2-ctl commands
        self.src = src

        # Store exposure value - ADD DEBUG LOG
        self.exposure = exposure
        self.logger.info(f"ArducamStream initialized with exposure parameter: {exposure}")

        # Color adjustment factors (set BEFORE frame processing)
        self.green_factor = kwargs.get('green_factor', 1.0)
        self.red_factor = kwargs.get('red_factor', 1.1)
        self.blue_factor = kwargs.get('blue_factor', 1.25)
        self.brightness_alpha = kwargs.get('brightness_alpha', 1.2)
        self.brightness_beta = kwargs.get('brightness_beta', 30)

        # Get frame dimensions
        self.frame_width = resolution[0]
        self.frame_height = resolution[1]

        # Initialize camera with V4L2 backend
        self.stream = cv2.VideoCapture(src, cv2.CAP_V4L2)

        # Initialize ArducamUtils
        try:
            self.arducam_utils = ArducamUtils(src)
            self.logger.info("ArducamUtils initialized successfully")

            # Log pixel format information
            pixfmts = self.arducam_utils.get_pixelformats()
            self.logger.info(f"Available pixel formats: {len(pixfmts)}")
            for fmt, desc in pixfmts:
                self.logger.debug(f"  Format: {fmt:08x} - {desc}")

        except Exception as e:
            self.logger.error(f"Failed to initialize ArducamUtils: {e}")
            self.stream.release()
            raise ValueError(f"Failed to initialize ArducamUtils: {e}")

        # Turn off RGB conversion to handle raw data
        self.stream.set(cv2.CAP_PROP_CONVERT_RGB, self.arducam_utils.convert2rgb)
        self.logger.info(f"RGB conversion setting: {self.arducam_utils.convert2rgb}")

        # Check if the stream opened successfully
        if not self.stream.isOpened():
            self.stream.release()
            self.logger.error(f'Unable to open Arducam video source: {src}')
            raise ValueError("Unable to open Arducam video source:", src)

        # Give camera time to initialize properly
        time.sleep(0.5)

        # Set exposure once, cleanly
        self._set_initial_exposure(exposure)

        # read the first frame from the stream
        self.grabbed, self.frame = self.stream.read()
        if not self.grabbed:
            self.stream.release()
            self.logger.error(f'Unable to read from Arducam video source: {src}')
            raise ValueError("Unable to read from Arducam video source:", src)

        # Log initial frame info
        if self.frame is not None:
            self.logger.info(f"Initial frame shape: {self.frame.shape}, dtype: {self.frame.dtype}")

        # Process the first frame to ensure ArducamUtils works
        try:
            self.frame = self._process_frame(self.frame)
            if self.frame is not None:
                self.logger.info(f"Processed frame shape: {self.frame.shape}, dtype: {self.frame.dtype}")
        except Exception as e:
            self.logger.error(f"Failed to process initial frame: {e}")
            self.stream.release()
            raise ValueError(f"Failed to process initial frame: {e}")

        # initialize the thread name, stop event, and the thread itself
        self.stop_event = Event()
        self.thread = Thread(target=self.update, name=self.name, args=())
        self.thread.daemon = True

    def _set_initial_exposure(self, exposure_value):
        """Set initial exposure using sensor register method (0x3012)"""
        self.logger.info(f"Setting initial exposure to {exposure_value} using sensor register 0x3012")
        
        try:
            # Read current exposure
            current_exp = self.arducam_utils.read_sensor(0x3012)
            self.logger.info(f"Current exposure register 0x3012: {current_exp}")
            
            # Write new exposure value
            self.arducam_utils.write_sensor(0x3012, exposure_value)
            time.sleep(0.1)  # Give sensor time to process
            
            # Verify the write
            verify_exp = self.arducam_utils.read_sensor(0x3012)
            self.logger.info(f"Exposure set: {current_exp} -> {verify_exp} (requested: {exposure_value})")
            
            if verify_exp != 65534 and verify_exp != 0xFFFF:
                self.logger.info("✅ Initial exposure set successfully via sensor register!")
                return True
            else:
                self.logger.warning("Sensor register still returning invalid value")
                return False
                
        except Exception as e:
            self.logger.warning(f"Failed to set initial exposure via sensor register: {e}")
            return False


    def _process_frame(self, frame):
        """Process frame using ArducamUtils and apply color corrections"""
        if frame is None or frame.size == 0:
            return None

        try:
            # Apply ArducamUtils conversion - this handles Bayer to BGR conversion
            converted_frame = self.arducam_utils.convert(frame)
            if converted_frame is None:
                self.logger.warning("ArducamUtils conversion returned None, using original frame")
                converted_frame = frame

            # Apply brightness adjustment
            adjusted_frame = cv2.convertScaleAbs(converted_frame, alpha=self.brightness_alpha, beta=self.brightness_beta)

            # Apply color corrections if it's a color image
            if len(adjusted_frame.shape) == 3 and adjusted_frame.shape[2] == 3:
                # Create a copy to avoid modifying the original
                color_corrected = adjusted_frame.copy().astype(np.float32)

                # Apply color factors
                color_corrected[:,:,0] = np.clip(color_corrected[:,:,0] * self.blue_factor, 0, 255)   # Blue channel
                color_corrected[:,:,1] = np.clip(color_corrected[:,:,1] * self.green_factor, 0, 255)  # Green channel
                color_corrected[:,:,2] = np.clip(color_corrected[:,:,2] * self.red_factor, 0, 255)   # Red channel

                adjusted_frame = color_corrected.astype(np.uint8)

            # Resize if needed
            if (adjusted_frame.shape[1], adjusted_frame.shape[0]) != (self.frame_width, self.frame_height):
                adjusted_frame = cv2.resize(adjusted_frame, (self.frame_width, self.frame_height))

            return adjusted_frame

        except Exception as e:
            self.logger.error(f"Frame processing error: {e}")
            # Return original frame if processing fails
            if (frame.shape[1], frame.shape[0]) != (self.frame_width, self.frame_height):
                return cv2.resize(frame, (self.frame_width, self.frame_height))
            return frame

    def start(self):
        self.thread.start()
        return self

    def update(self):
        # keep looping infinitely until the thread is stopped
        frame_count = 0
        try:
            while not self.stop_event.is_set():
                # Read the next frame from the stream
                self.grabbed, raw_frame = self.stream.read()

                # If not grabbed, end of the stream has been reached.
                if not self.grabbed:
                    self.stop_event.set()  # Ensure the loop stops if no frame is grabbed
                    break

                frame_count += 1
                
                # Maintain exposure every 10 frames using sensor register method
                if frame_count % 10 == 0:
                    try:
                        self.arducam_utils.write_sensor(0x3012, self.exposure)
                    except Exception as e:
                        self.logger.debug(f"Failed to maintain exposure: {e}")

                # Process the frame
                self.frame = self._process_frame(raw_frame)

        except Exception as e:
            self.logger.error(f"Exception in ArducamStream update loop: {e}", exc_info=True)
        finally:
            # Clean up resources after loop is done
            self.stream.release()

    def read(self):
        # return the frame most recently read
        return self.frame

    def stop(self):
        self.stop_event.set()
        self.thread.join()

    def set_exposure(self, exposure_value):
        """Set camera exposure using sensor register method (0x3012)"""
        self.logger.info(f"Setting exposure to {exposure_value}")

        try:
            # Read current exposure
            current_exp = self.arducam_utils.read_sensor(0x3012)
            
            # Write new exposure value
            self.arducam_utils.write_sensor(0x3012, exposure_value)
            time.sleep(0.05)  # Give sensor time to process
            
            # Verify the write
            verify_exp = self.arducam_utils.read_sensor(0x3012)
            self.logger.info(f"Sensor register exposure: {current_exp} -> {verify_exp}")

            if verify_exp != 65534 and verify_exp != 0xFFFF:
                # Update stored exposure value for continuous maintenance
                self.exposure = exposure_value
                self.logger.info("✅ Exposure set successfully via sensor register!")
                return True
            else:
                self.logger.warning("Sensor register returned invalid value")
                return False
                
        except Exception as e:
            self.logger.warning(f"Failed to set exposure via sensor register: {e}")
            return False

    def get_exposure(self):
        """Get current camera exposure using sensor register method"""
        try:
            sensor_exp = self.arducam_utils.read_sensor(0x3012)
            if sensor_exp != 65534 and sensor_exp != 0xFFFF:
                return sensor_exp
            else:
                self.logger.debug("Sensor register returned invalid value")
                return None
        except Exception as e:
            self.logger.debug(f"Failed to read exposure from sensor register: {e}")
            return None
    
    def adjust_exposure(self, delta):
        """Adjust exposure by a delta amount (like +/- keys in your example)"""
        try:
            current_exp = self.arducam_utils.read_sensor(0x3012)
            if current_exp == 65534 or current_exp == 0xFFFF:
                self.logger.warning("Cannot adjust exposure - invalid current value")
                return False
                
            # Calculate new exposure with bounds checking
            new_exposure = max(100, min(current_exp + delta, 10000))
            
            # Set the new exposure
            success = self.set_exposure(new_exposure)
            if success:
                self.logger.info(f"Exposure adjusted: {current_exp} -> {new_exposure} (delta: {delta})")
            return success
            
        except Exception as e:
            self.logger.warning(f"Failed to adjust exposure: {e}")
            return False


# overarching class to determine which stream to use
class VideoStream:
    def __init__(self, src=0, resolution=(416, 320), exp_compensation=-2, **kwargs):
        self.logger = LogManager.get_logger(__name__)
        self.frame_height = None
        self.frame_width = None

        # Jetson-only camera initialization
        # Priority order: ArducamUtils > Jetson CSI > Webcam fallback
        arducam_initialized = False
        
        if ARDUCAM_AVAILABLE:
            # Try ArducamUtils first if available
            try:
                self.CAMERA_VERSION = 'arducam'
                self.stream = ArducamStream(src=src, resolution=resolution, **kwargs)
                self.logger.info("Using Arducam camera with ArducamUtils")
                arducam_initialized = True
            except Exception as e:
                self.logger.warning(f"Failed to initialize Arducam camera: {e}")
                self.logger.info("Falling back to Jetson CSI camera")
                arducam_initialized = False
        
        if not arducam_initialized:
            if JETSON_PLATFORM:
                # On Jetson, try CSI camera, fallback to webcam
                try:
                    self.CAMERA_VERSION = 'jetson_csi'
                    self.stream = JetsonCSIStream(sensor_id=src, resolution=resolution, **kwargs)
                    self.logger.info("Using Jetson CSI camera")
                except Exception as e:
                    self.logger.warning(f"Failed to initialize Jetson CSI camera: {e}")
                    self.logger.info("Falling back to webcam")
                    self.CAMERA_VERSION = 'webcam'
                    self.stream = WebcamStream(src=src)
            else:
                # Not on Jetson platform, use webcam
                self.logger.info("Not on Jetson platform, using webcam")
                self.CAMERA_VERSION = 'webcam'
                self.stream = WebcamStream(src=src)

        # set the image dimensions directly from the frame streamed
        self.frame_width = self.stream.frame_width
        self.frame_height = self.stream.frame_height

    def start(self):
        # start the threaded video stream
        return self.stream.start()

    def update(self):
        # grab the next frame from the stream
        self.stream.update()

    def read(self):
        # return the current frame
        return self.stream.read()

    def stop(self):
        # stop the thread and release any resources
        self.stream.stop()
    
    def set_exposure(self, exposure_value):
        """Set camera exposure (only available for ArducamStream)"""
        if hasattr(self.stream, 'set_exposure'):
            return self.stream.set_exposure(exposure_value)
        else:
            self.logger.warning("Exposure control not available for current camera type")
            return False
    
    def get_exposure(self):
        """Get current camera exposure (only available for ArducamStream)"""
        if hasattr(self.stream, 'get_exposure'):
            return self.stream.get_exposure()
        else:
            self.logger.warning("Exposure reading not available for current camera type")
            return None
    
    def adjust_exposure(self, delta):
        """Adjust camera exposure by delta amount (only available for ArducamStream)"""
        if hasattr(self.stream, 'adjust_exposure'):
            return self.stream.adjust_exposure(delta)
        else:
            self.logger.warning("Exposure adjustment not available for current camera type")
            return False
