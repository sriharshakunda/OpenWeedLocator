#!/usr/bin/env python

import cv2
import time
import argparse
import imutils
from utils.greenonbrown import GreenOnBrown
from utils.blur_algorithms import fft_blur
import sys
from configparser import ConfigParser
from pathlib import Path

def nothing(x):
    pass

class Owl:
    def __init__(self, show_display=False, focus=False, input_file_or_directory=None, config_file='config/DAY_SENSITIVITY_2.ini'):
        # start by reading the config file
        self._config_path = Path(__file__).parent / config_file
        self.config = ConfigParser()
        self.config.read(self._config_path)

        # is the source a directory/file
        self.input_file_or_directory = input_file_or_directory

        # visualise the detections with video feed
        self.show_display = show_display

        # WARNING: option disable detection for data collection
        self.disable_detection = False

        self.focus = focus
        if self.focus:
            self.show_display = True

        self.resolution = (self.config.getint('Camera', 'resolution_width'), self.config.getint('Camera', 'resolution_height'))
        self.exp_compensation = self.config.getint('Camera', 'exp_compensation')

        # threshold parameters for different algorithms
        self.exgMin = self.config.getint('GreenOnBrown', 'exgMin')
        self.exgMax = self.config.getint('GreenOnBrown', 'exgMax')
        self.hueMin = self.config.getint('GreenOnBrown', 'hueMin')
        self.hueMax = self.config.getint('GreenOnBrown', 'hueMax')
        self.saturationMin = self.config.getint('GreenOnBrown', 'saturationMin')
        self.saturationMax = self.config.getint('GreenOnBrown', 'saturationMax')
        self.brightnessMin = self.config.getint('GreenOnBrown', 'brightnessMin')
        self.brightnessMax = self.config.getint('GreenOnBrown', 'brightnessMax')

        self.threshold_dict = {}
        # time spent on each image when looping over a directory
        self.image_loop_time = self.config.getint('Visualisation', 'image_loop_time')

        # setup the track bars if show_display is True
        if self.show_display:
            # create trackbars for the threshold calculation
            self.window_name = "Adjust Detection Thresholds"
            cv2.namedWindow("Adjust Detection Thresholds", cv2.WINDOW_AUTOSIZE)
            cv2.createTrackbar("ExG-Min", self.window_name, self.exgMin, 255, nothing)
            cv2.createTrackbar("ExG-Max", self.window_name, self.exgMax, 255, nothing)
            cv2.createTrackbar("Hue-Min", self.window_name, self.hueMin, 179, nothing)
            cv2.createTrackbar("Hue-Max", self.window_name, self.hueMax, 179, nothing)
            cv2.createTrackbar("Sat-Min", self.window_name, self.saturationMin, 255, nothing)
            cv2.createTrackbar("Sat-Max", self.window_name, self.saturationMax, 255, nothing)
            cv2.createTrackbar("Bright-Min", self.window_name, self.brightnessMin, 255, nothing)
            cv2.createTrackbar("Bright-Max", self.window_name, self.brightnessMax, 255, nothing)

        # check that the resolution is not so high it will entirely brick/destroy the OWL.
        total_pixels = self.resolution[0] * self.resolution[1]
        if total_pixels > (832 * 640):
            # change here if you want to test higher resolutions, but be warned, backup your current image!
            self.resolution = (416, 320)
            print(f"[WARNING] Resolution {self.config.getint('Camera', 'resolution_width')}, {self.config.getint('Camera', 'resolution_height')} selected is dangerously high.")

        # check if test video or videostream from camera
        # is the source a directory/file
        if len(self.config.get('System', 'input_file_or_directory')) > 0:
            self.input_file_or_directory = self.config.get('System', 'input_file_or_directory')

        self.input_file_or_directory = input_file_or_directory

        if len(self.config.get('System', 'input_file_or_directory')) > 0 and input_file_or_directory is not None:
            print('[WARNING] two paths to image/videos provided. Defaulting to the command line flag.')

        if self.input_file_or_directory:
            self.cam = cv2.VideoCapture(self.input_file_or_directory)
            self.frame_width = int(self.cam.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.frame_height = int(self.cam.get(cv2.CAP_PROP_FRAME_HEIGHT))

            print(f'[INFO] Using input from {self.input_file_or_directory}...')

        # if no video, start the camera with the provided parameters
        else:
            try:
                gst_str = f"nvarguscamerasrc ! video/x-raw(memory:NVMM), width=(int){self.resolution[0]}, height=(int){self.resolution[1]}, format=(string)NV12, framerate=(fraction)30/1 ! nvvidconv flip-method=2 ! video/x-raw, format=(string)BGRx ! videoconvert ! video/x-raw, format=(string)BGR ! appsink"
                self.cam = cv2.VideoCapture(gst_str, cv2.CAP_GSTREAMER)

                self.frame_width = self.resolution[0]
                self.frame_height = self.resolution[1]

            except Exception as e:
                print(f"[CRITICAL ERROR] Stopped OWL at start: {e}")
                time.sleep(2)
                sys.exit(1)

        time.sleep(1.0)

        # sensitivity and weed size to be added
        self.sensitivity = None
        self.lane_coords = {}

        # add the total number of relays being controlled. This can be changed easily, but the relay_dict and physical relays would need
        # to be updated too. Fairly straightforward, so an opportunity for more precise application
        self.relay_num = self.config.getint('System', 'relay_num')

        # activation region limit - once weed crosses this line, relay is activated
        self.yAct = int(0.01 * self.frame_height)
        self.lane_width = self.frame_width / self.relay_num

        # calculate lane coords and draw on frame
        for i in range(self.relay_num):
            laneX = int(i * self.lane_width)
            self.lane_coords[i] = laneX

    def hoot(self):
        algorithm = self.config.get('System', 'algorithm')
        log_fps = self.config.getboolean('DataCollection', 'log_fps')

        # track FPS and framecount
        frame_count = 0

        if log_fps:
            fps = FPS().start()

        try:
            min_detection_area = self.config.getint('GreenOnBrown', 'min_detection_area')
            invert_hue = self.config.getboolean('GreenOnBrown', 'invert_hue')

            weed_detector = GreenOnBrown()

        except Exception as e:
            print(f"\n[ALGORITHM ERROR] Unrecognised error while starting algorithm: {algorithm}.\nError message: {e}")
            self.stop()

        if self.show_display:
            pass

        try:
            while True:
                ret, frame = self.cam.read()

                if not ret:
                    print("[INFO] Frame is None. Stopped.")
                    self.stop()
                    break

                if self.show_display:
                    self.exgMin = cv2.getTrackbarPos("ExG-Min", self.window_name)
                    self.exgMax = cv2.getTrackbarPos("ExG-Max", self.window_name)
                    self.hueMin = cv2.getTrackbarPos("Hue-Min", self.window_name)
                    self.hueMax = cv2.getTrackbarPos("Hue-Max", self.window_name)
                    self.saturationMin = cv2.getTrackbarPos("Sat-Min", self.window_name)
                    self.saturationMax = cv2.getTrackbarPos("Sat-Max", self.window_name)
                    self.brightnessMin = cv2.getTrackbarPos("Bright-Min", self.window_name)
                    self.brightnessMax = cv2.getTrackbarPos("Bright-Max", self.window_name)
                else:
                    self.update(exgMin=self.exgMin, exgMax=self.exgMax)

                # pass image, thresholds to green_on_brown function
                if not self.disable_detection:
                    cnts, boxes, weed_centres, image_out = weed_detector.inference(frame,
                                                                                   exgMin=self.exgMin,
                                                                                   exgMax=self.exgMax,
                                                                                   hueMin=self.hueMin,
                                                                                   hueMax=self.hueMax,
                                                                                   saturationMin=self.saturationMin,
                                                                                   saturationMax=self.saturationMax,
                                                                                   brightnessMin=self.brightnessMin,
                                                                                   brightnessMax=self.brightnessMax,
                                                                                   show_display=self.show_display,
                                                                                   algorithm=algorithm,
                                                                                   min_detection_area=min_detection_area,
                                                                                   invert_hue=invert_hue,
                                                                                   label='WEED')

                ##### IMAGE SAMPLER #####
                # record sample images if required of weeds detected. sampleFreq specifies how often
                frame_count += 1
                if log_fps and frame_count % 900 == 0:
                    fps.stop()
                    print(f"[INFO] Approximate FPS: {fps.fps():.2f}")
                    fps = FPS().start()

                # update the framerate counter
                if log_fps:
                    fps.update()

                if self.show_display:
                    if self.disable_detection:
                        image_out = frame.copy()

                    cv2.putText(image_out, f'OWL-gorithm: {algorithm}', (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (80, 80, 255), 1)
                    cv2.putText(image_out, f'Press "S" to save {algorithm} thresholds to file.',
                                (20, int(image_out.shape[1] * 0.72)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 80, 255), 1)
                    if self.focus:
                        cv2.putText(image_out, f'Blurriness: {fft_blur(cv2.cvtColor(frame.copy(), cv2.COLOR_BGR2GRAY), size=30):.2f}', (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (80, 80, 255), 1)

                    cv2.imshow("Detection Output", imutils.resize(image_out, width=600))

                k = cv2.waitKey(1) & 0xFF
                if k == ord('s'):
                    self.save_parameters()
                    print("[INFO] Parameters saved.")

                if k == 27:
                    if log_fps:
                        fps.stop()
                        print(f"[INFO] Approximate FPS: {fps.fps():.2f}")
                    if self.show_display:
                        pass

                    print("[INFO] Stopped.")
                    self.stop()
                    break

        except KeyboardInterrupt:
            if log_fps:
                fps.stop()
                print(f"[INFO] Approximate FPS: {fps.fps():.2f}")
            if self.show_display:
                pass
            print("[INFO] Stopped.")
            self.stop()

        except Exception as e:
            print(f"[CRITICAL ERROR] STOPPED: {e}")
            self.stop()

    def stop(self):
        self.cam.release()
        if self.show_display:
            cv2.destroyAllWindows()
        sys.exit()

    def update(self, exgMin=30, exgMax=180):
        self.exgMin = exgMin
        self.exgMax = exgMax

    def save_parameters(self):
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        new_config_filename = f"{timestamp}_{self._config_path.name}"
        new_config_path = self._config_path.parent / new_config_filename

        # Update the 'GreenOnBrown' section with current attribute values
        if 'GreenOnBrown' not in self.config.sections():
            self.config.add_section('GreenOnBrown')

        self.config.set('GreenOnBrown', 'exgMin', str(self.exgMin))
        self.config.set('GreenOnBrown', 'exgMax', str(self.exgMax))
        self.config.set('GreenOnBrown', 'hueMin', str(self.hueMin))
        self.config.set('GreenOnBrown', 'hueMax', str(self.hueMax))
        self.config.set('GreenOnBrown', 'saturationMin', str(self.saturationMin))
        self.config.set('GreenOnBrown', 'saturationMax', str(self.saturationMax))
        self.config.set('GreenOnBrown', 'brightnessMin', str(self.brightnessMin))
        self.config.set('GreenOnBrown', 'brightnessMax', str(self.brightnessMax))

        # Write the updated configuration to the new file with a timestamped filename
        with open(new_config_path, 'w') as configfile:
            self.config.write(configfile)

        print(f"[INFO] Configuration saved to {new_config_path}")

# business end of things
if __name__ == "__main__":
    # these command line arguments enable people to operate/change some settings from the command line instead of
    # opening up the OWL code each time.
    ap = argparse.ArgumentParser()
    ap.add_argument('--show-display', action='store_true', default=False, help='show display windows')
    ap.add_argument('--focus', action='store_true', default=False, help='add FFT blur to output frame')
    ap.add_argument('--input', type=str, default=None, help='path to image directory, single image or video file')

    args = ap.parse_args()

    # this is where you can change the config file default
    owl = Owl(config_file='config/DAY_SENSITIVITY_2.ini',
              show_display=args.show_display,
              focus=args.focus,
              input_file_or_directory=args.input)

    # start the targeting!
    owl.hoot()

