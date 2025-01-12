import cv2
import time
from threading import Thread, Event, Lock
from utils.log_manager import LogManager


# Define GStreamer pipeline
gst_pipeline = (
    "nvarguscamerasrc ! "
    "video/x-raw(memory:NVMM), width=1280, height=720, framerate=30/1 ! "
    "nvvidconv ! "
    "video/x-raw, format=BGRx ! "
    "videoconvert ! "
    "video/x-raw, format=BGR ! appsink"
)


# Class to support GStreamer pipelines
class GStreamerStream:
    def __init__(self, pipeline=gst_pipeline, resolution=(1280, 720)):
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
    def __init__(self, src=gst_pipeline, resolution=(1280, 720), **kwargs):
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
        if isinstance(src, str) and src.startswith('nvarguscamerasrc'):
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