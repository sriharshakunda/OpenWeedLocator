import cv2
import time
from threading import Thread, Event, Lock
from utils.log_manager import LogManager


# Define GStreamer pipelines
pipeline = {
    "default_camera": "gst-launch-1.0 v4l2src ! video/x-raw, width=640, height=480 ! videoconvert ! appsink",
    "custom_pipeline": "gst-launch-1.0 v4l2src device=/dev/video0 ! video/x-raw, width=1280, height=720 ! videoconvert ! appsink"
}


# Class to support webcams
class WebcamStream:
    def __init__(self, src=0, resolution=(640, 480)):
        """
        Initialize the webcam stream.
        :param src: Camera index or video file path.
        :param resolution: Tuple (width, height) for the frame resolution.
        """
        self.logger = LogManager.get_logger(__name__)
        self.name = "WebcamStream"
        self.logger.info(f'Camera type: {self.name}')
        self.stream = cv2.VideoCapture(src)
        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])

        self.frame_width = self.stream.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.frame_height = self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT)

        # Check if the stream opened successfully
        if not self.stream.isOpened():
            self.stream.release()
            self.logger.error(f'Unable to open video source: {src}')
            raise ValueError("Unable to open video source:", src)

        # Read the first frame from the stream
        self.grabbed, self.frame = self.stream.read()
        if not self.grabbed:
            self.stream.release()
            self.logger.error(f'Unable to read from video source: {src}')
            raise ValueError("Unable to read from video source:", src)

        # Initialize the thread name, stop event, and the thread itself
        self.stop_event = Event()
        self.lock = Lock()
        self.thread = Thread(target=self.update, name=self.name, args=())
        self.thread.daemon = True

    def start(self):
        """
        Start the thread to read frames from the stream.
        """
        self.thread.start()
        return self

    def update(self):
        """
        Continuously read frames from the stream.
        """
        try:
            while not self.stop_event.is_set():
                # Read the next frame from the stream
                grabbed, frame = self.stream.read()

                # If not grabbed, end of the stream has been reached.
                if not grabbed:
                    self.stop_event.set()  # Ensure the loop stops if no frame is grabbed
                    break

                with self.lock:
                    self.frame = frame

        except Exception as e:
            self.logger.error(f"Exception in WebcamStream update loop: {e}", exc_info=True)
            self.stop_event.set()
        finally:
            # Clean up resources after loop is done
            self.stream.release()

    def read(self):
        """
        Return the most recently read frame.
        """
        with self.lock:
            return self.frame

    def stop(self):
        """
        Stop the thread and release resources.
        """
        if not self.stop_event.is_set():
            self.stop_event.set()
            self.thread.join()


# Class to support GStreamer pipelines
class GStreamerStream:
    def __init__(self, pipeline, resolution=(640, 480)):
        """
        Initialize the GStreamer stream.
        :param pipeline: GStreamer pipeline string.
        :param resolution: Tuple (width, height) for the frame resolution.
        """
        self.logger = LogManager.get_logger(__name__)
        self.name = "GStreamerStream"
        self.logger.info(f'Camera type: {self.name}')
        self.resolution = resolution

        # Initialize the GStreamer pipeline
        self.stream = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        if not self.stream.isOpened():
            self.logger.error(f"Failed to open GStreamer pipeline: {pipeline}")
            raise ValueError(f"Failed to open GStreamer pipeline: {pipeline}")

        # Set frame dimensions
        self.frame_width = resolution[0]
        self.frame_height = resolution[1]

        # Initialize the frame and stop event
        self.frame = None
        self.stop_event = Event()
        self.lock = Lock()
        self.thread = Thread(target=self.update, name=self.name, args=())
        self.thread.daemon = True

    def start(self):
        """
        Start the thread to read frames from the GStreamer pipeline.
        """
        self.thread.start()
        return self

    def update(self):
        """
        Continuously read frames from the GStreamer pipeline.
        """
        try:
            while not self.stop_event.is_set():
                ret, frame = self.stream.read()
                if not ret:
                    self.logger.error("Failed to read frame from GStreamer pipeline")
                    self.stop_event.set()
                    break

                # Resize the frame to the specified resolution
                frame = cv2.resize(frame, self.resolution)
                with self.lock:
                    self.frame = frame

        except Exception as e:
            self.logger.error(f"Exception in GStreamerStream update loop: {e}", exc_info=True)
            self.stop_event.set()
        finally:
            self.stream.release()

    def read(self):
        """
        Return the most recently read frame.
        """
        with self.lock:
            return self.frame

    def stop(self):
        """
        Stop the thread and release resources.
        """
        if not self.stop_event.is_set():
            self.stop_event.set()
            self.thread.join()


# Overarching class to determine which stream to use
class VideoStream:
    def __init__(self, src=0, resolution=(640, 480), **kwargs):
        """
        Initialize the VideoStream class.
        :param src: GStreamer pipeline string, camera index, or video file path.
        :param resolution: Tuple (width, height) for the frame resolution.
        :param kwargs: Additional arguments (unused in this implementation).
        """
        self.logger = LogManager.get_logger(__name__)
        self.frame_height = None
        self.frame_width = None

        # Check if the source is a GStreamer pipeline
        if isinstance(src, str) and src.startswith('gst'):
            self.logger.info("Using GStreamer pipeline")
            self.stream = GStreamerStream(pipeline=src, resolution=resolution)
        else:
            # Use WebcamStream for non-GStreamer sources (e.g., camera index or video file)
            self.logger.info("Using WebcamStream")
            self.stream = WebcamStream(src=src, resolution=resolution)

        # Set the image dimensions directly from the frame streamed
        self.frame_width = self.stream.frame_width
        self.frame_height = self.stream.frame_height

    def start(self):
        """
        Start the threaded video stream.
        """
        return self.stream.start()

    def read(self):
        """
        Return the current frame.
        """
        return self.stream.read()

    def stop(self):
        """
        Stop the thread and release any resources.
        """
        self.stream.stop()