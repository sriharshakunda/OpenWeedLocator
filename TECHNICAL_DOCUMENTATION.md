# OpenWeedLocator Technical Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Main Application Flow (owl.py)](#main-application-flow-owlpy)
3. [Core Components](#core-components)
4. [Camera System (video_manager.py)](#camera-system-video_managerpy)
5. [Detection Algorithms](#detection-algorithms)
6. [Using Green-on-Green Instead of Green-on-Brown](#using-green-on-green-instead-of-green-on-brown)
7. [Using Your Own Custom Model](#using-your-own-custom-model)
8. [Configuration System](#configuration-system)
9. [GPIO and Hardware Control](#gpio-and-hardware-control)
10. [Troubleshooting and Debugging](#troubleshooting-and-debugging)

---

## System Overview

OpenWeedLocator (OWL) is a precision agriculture system designed to detect and target weeds in crop fields. The system uses computer vision algorithms to identify weeds and controls hardware (relays, nozzles) to apply targeted treatment.

### High-Level Architecture
```
owl.py (Main Application)
├── VideoStream (Camera Input)
├── Detection Algorithms (Computer Vision)
├── RelayController (Hardware Output)
├── StatusIndicator (User Feedback)
└── Configuration Management
```

---

## Main Application Flow (owl.py)

### 1. Application Initialization

The main entry point is `owl.py`, which starts with the `Owl` class:

```python
class Owl:
    def __init__(self, config_path, input_file_or_directory=None, show_display=False):
        # Initialize logging system
        self.logger = LogManager.get_logger(__name__)
        
        # Load configuration
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
        
        # Platform detection (Jetson-optimized)
        self.BOARD_VERSION = get_board_version()
        self.PLATFORM_TYPE = get_platform_type()
```

**Key Functions:**
- `LogManager.get_logger()`: Sets up logging system
- `get_board_version()`: Detects Jetson board type
- `configparser.ConfigParser()`: Loads .ini configuration files

### 2. Camera System Setup

```python
def setup_media_source(self):
    """Initialize camera with Arducam support"""
    self.stream = VideoStream(
        src=0,
        resolution=self.resolution,
        exposure=self.arducam_exposure,
        arducam_green_factor=self.arducam_green_factor,
        # ... other Arducam parameters
    )
```

**Key Functions:**
- `VideoStream()`: Main camera interface (supports Arducam, Jetson CSI, Webcam)
- Automatic camera priority: Arducam → Jetson CSI → Webcam fallback

### 3. Hardware Controllers Setup

```python
# Output control (relays, nozzles)
self.relay_controller = RelayController(
    pin_one=self.config.getint('Relays', 'pin_one'),
    pin_two=self.config.getint('Relays', 'pin_two'),
    # ...
)

# Input control (buttons, switches)
self.input_controller = UteController() or AdvancedController()

# Status indicators (LEDs)
self.status_indicator = UteStatusIndicator() or AdvancedStatusIndicator()
```

### 4. Main Processing Loop

```python
def run(self):
    """Main detection and control loop"""
    
    # Start all systems
    self.stream.start()
    self.status_indicator.start()
    
    # Main processing loop
    while not self.stopped:
        # 1. Capture frame
        image = self.stream.read()
        
        # 2. Apply detection algorithm
        predictions = self.detect_weeds(image)
        
        # 3. Control hardware based on predictions
        self.relay_controller.update_relays(predictions)
        
        # 4. Update display/logging
        if self.show_display:
            self.display_results(image, predictions)
```

---

## Core Components

### Detection Pipeline

The system uses a multi-stage detection pipeline:

1. **Frame Acquisition**: Camera captures raw frame
2. **Preprocessing**: Color correction, brightness adjustment
3. **Algorithm Selection**: Choose detection method based on config
4. **Weed Detection**: Apply selected algorithm
5. **Hardware Control**: Activate relays based on detections

### Key Classes and Their Roles

| Class | File | Purpose |
|-------|------|---------|
| `Owl` | owl.py | Main application controller |
| `VideoStream` | utils/video_manager.py | Camera interface abstraction |
| `ArducamStream` | utils/video_manager.py | Arducam camera implementation |
| `RelayController` | utils/output_manager.py | Hardware output control |
| `UteController` | utils/input_manager.py | Hardware input handling |
| `LogManager` | utils/log_manager.py | Logging system |

---

## Camera System (video_manager.py)

### VideoStream Architecture

The camera system uses a hierarchical approach:

```python
class VideoStream:
    """Main camera interface - automatically selects best available camera"""
    
    def __init__(self, src=0, resolution=(416, 320), **kwargs):
        # Priority order: ArducamUtils > Jetson CSI > Webcam
        if ARDUCAM_AVAILABLE:
            self.stream = ArducamStream(src=src, resolution=resolution, **kwargs)
        elif JETSON_PLATFORM:
            self.stream = JetsonCSIStream(sensor_id=src, resolution=resolution, **kwargs)
        else:
            self.stream = WebcamStream(src=src)
```

### ArducamStream Implementation

**Key Features:**
- **Continuous Exposure Control**: Maintains exposure every 10 frames using sensor register 0x3012
- **Color Processing**: Bayer to BGR conversion with color correction
- **Threading**: Runs camera capture in separate thread for performance

```python
class ArducamStream:
    def update(self):
        """Main camera loop with continuous exposure maintenance"""
        frame_count = 0
        while not self.stop_event.is_set():
            # Capture frame
            self.grabbed, raw_frame = self.stream.read()
            
            # Maintain exposure every 10 frames
            if frame_count % 10 == 0:
                self.arducam_utils.write_sensor(0x3012, self.exposure)
            
            # Process frame (Bayer → BGR, color correction)
            self.frame = self._process_frame(raw_frame)
            frame_count += 1
```

**Exposure Control Methods:**
- `set_exposure(value)`: Set exposure to specific value
- `get_exposure()`: Read current exposure from sensor
- `adjust_exposure(delta)`: Adjust exposure by delta amount (+/- controls)

### Frame Processing Pipeline

```python
def _process_frame(self, frame):
    """Arducam frame processing pipeline"""
    
    # 1. Bayer to BGR conversion
    converted_frame = self.arducam_utils.convert(frame)
    
    # 2. Brightness adjustment
    adjusted_frame = cv2.convertScaleAbs(converted_frame, 
                                        alpha=self.brightness_alpha, 
                                        beta=self.brightness_beta)
    
    # 3. Color correction
    if len(adjusted_frame.shape) == 3:
        adjusted_frame[:,:,0] *= self.blue_factor   # Blue channel
        adjusted_frame[:,:,1] *= self.green_factor  # Green channel  
        adjusted_frame[:,:,2] *= self.red_factor    # Red channel
    
    # 4. Resize to target resolution
    return cv2.resize(adjusted_frame, (self.frame_width, self.frame_height))
```

---

## Detection Algorithms

### Available Detection Methods

The system supports multiple detection algorithms:

1. **Green-on-Brown (Default)**: Detects green vegetation on brown soil
2. **Green-on-Green**: Detects weeds in green crop fields
3. **HSV Threshold**: Color-based detection using HSV color space
4. **Machine Learning**: TensorFlow Lite models for advanced detection

### Algorithm Selection

```python
def detect_weeds(self, image):
    """Main detection dispatcher"""
    
    algorithm = self.config.get('Targeting', 'algorithm')
    
    if algorithm == 'gog':
        return self.greenongreen_detection(image)
    elif algorithm == 'gob':
        return self.greenonbrown_detection(image)
    elif algorithm == 'hsv':
        return self.hsv_detection(image)
    elif algorithm == 'ml':
        return self.ml_detection(image)
```

### Detection Output Format

All detection algorithms return a standardized format:

```python
{
    'detections': [
        {
            'confidence': 0.85,
            'bbox': [x1, y1, x2, y2],
            'center': [cx, cy],
            'nozzle_zone': 1  # Which nozzle should activate
        }
    ],
    'total_detections': 3,
    'processing_time_ms': 45.2
}
```

---

## Using Green-on-Green Instead of Green-on-Brown

### Configuration Changes

To switch from green-on-brown to green-on-green detection:

#### 1. Update Algorithm in Configuration

Edit your config file (e.g., `config/DAY_SENSITIVITY_2.ini`):

```ini
[Targeting]
# Change from 'gob' to 'gog'
algorithm = gog

# Green-on-green specific parameters
gog_hue_min = 30
gog_hue_max = 85
gog_saturation_min = 40
gog_saturation_max = 255
gog_value_min = 40
gog_value_max = 255

# Morphological operations for noise reduction
gog_erode_iterations = 2
gog_dilate_iterations = 2
gog_blur_kernel = 5

# Size filtering
gog_min_detection_area = 100
gog_max_detection_area = 5000
```

#### 2. Green-on-Green Algorithm Parameters

**Key Parameters Explained:**

| Parameter | Description | Typical Range |
|-----------|-------------|---------------|
| `gog_hue_min/max` | Green hue range in HSV | 30-85 (covers yellow-green to blue-green) |
| `gog_saturation_min/max` | Color saturation threshold | 40-255 (excludes pale/gray areas) |
| `gog_value_min/max` | Brightness threshold | 40-255 (excludes shadows) |
| `gog_erode_iterations` | Noise removal strength | 1-3 iterations |
| `gog_dilate_iterations` | Gap filling strength | 1-3 iterations |
| `gog_min_detection_area` | Minimum weed size (pixels) | 50-200 pixels |

#### 3. Algorithm Implementation

### Traditional Green-on-Green (HSV-based)

The green-on-green algorithm (`utils/greenongreen_jetson.py`) works by:

```python
def detect_greenongreen(image, parameters):
    """Green-on-green detection algorithm"""
    
    # 1. Convert to HSV color space
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # 2. Create mask for green vegetation
    lower_green = np.array([parameters['hue_min'], 
                           parameters['saturation_min'], 
                           parameters['value_min']])
    upper_green = np.array([parameters['hue_max'], 
                           parameters['saturation_max'], 
                           parameters['value_max']])
    
    green_mask = cv2.inRange(hsv, lower_green, upper_green)
    
    # 3. Apply morphological operations
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
    
    # 4. Find contours (potential weeds)
    contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # 5. Filter by size and shape
    detections = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if parameters['min_area'] < area < parameters['max_area']:
            # Calculate bounding box and center
            x, y, w, h = cv2.boundingRect(contour)
            center_x, center_y = x + w//2, y + h//2
            
            detections.append({
                'bbox': [x, y, x+w, y+h],
                'center': [center_x, center_y],
                'confidence': min(area / parameters['max_area'], 1.0),
                'nozzle_zone': calculate_nozzle_zone(center_x, image.shape[1])
            })
    
    return {'detections': detections}
```

### YOLO-based Green-on-Green (Machine Learning)

The YOLO green-on-green algorithm (`utils/greenongreen_yolo.py`) uses deep learning for precise weed detection:

```python
def detect_weeds_yolo(image, model, parameters):
    """YOLO-based weed detection"""
    
    # 1. Preprocess image for YOLO input
    blob = cv2.dnn.blobFromImage(image, 1/255.0, (640, 640), 
                                swapRB=True, crop=False)
    
    # 2. Run inference
    model.setInput(blob)
    outputs = model.forward()
    
    # 3. Parse YOLO outputs (boxes, confidences, class_ids)
    detections = []
    for output in outputs:
        for detection in output:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            
            if confidence > parameters['confidence_threshold']:
                # Scale coordinates and filter by target classes
                center_x = int(detection[0] * image_width)
                center_y = int(detection[1] * image_height)
                width = int(detection[2] * image_width)
                height = int(detection[3] * image_height)
                
                # Calculate bounding box
                x = int(center_x - width / 2)
                y = int(center_y - height / 2)
                
                detections.append({
                    'bbox': [x, y, x + width, y + height],
                    'center': [center_x, center_y],
                    'confidence': float(confidence),
                    'class_id': class_id,
                    'class_name': get_class_name(class_id)
                })
    
    # 4. Apply Non-Maximum Suppression to remove duplicates
    filtered_detections = apply_nms(detections, parameters['nms_threshold'])
    
    return {'detections': filtered_detections}
```

**Crop-Specific Model Loading:**

```python
# Model selection based on crop type
crop_models = {
    'wheat': 'yolo_wheat_weeds.onnx',
    'corn': 'yolo_corn_weeds.onnx', 
    'soybean': 'yolo_soybean_weeds.onnx',
    'cotton': 'yolo_cotton_weeds.onnx',
    'general': 'yolo_general_weeds.onnx',
    'test': 'yolov8n.onnx'  # For testing
}

model_path = f"models/yolo/{crop_models[crop_type]}"
model = cv2.dnn.readNetFromONNX(model_path)
```

#### 4. Tuning Green-on-Green Parameters

**For Different Crop Types:**

| Crop Type | Hue Range | Saturation | Notes |
|-----------|-----------|------------|-------|
| **Wheat/Barley** | 35-80 | 30-255 | Mature crops have yellow tint |
| **Corn/Maize** | 30-85 | 40-255 | Broad green spectrum |
| **Soybeans** | 35-75 | 45-255 | Darker green leaves |
| **Cotton** | 30-80 | 35-255 | Light to medium green |

**Parameter Tuning Process:**

1. **Start with default parameters**
2. **Capture test images** in your field conditions
3. **Adjust hue range** based on crop color
4. **Fine-tune saturation** to exclude soil/shadows
5. **Optimize size filters** based on expected weed sizes

#### 5. Testing Green-on-Green

Create a test script to tune parameters:

```python
# test_greenongreen.py
import cv2
from utils.greenongreen import detect_greenongreen

# Load test image
image = cv2.imread('test_field_image.jpg')

# Test parameters
params = {
    'hue_min': 30,
    'hue_max': 85,
    'saturation_min': 40,
    'saturation_max': 255,
    'value_min': 40,
    'value_max': 255,
    'min_area': 100,
    'max_area': 5000
}

# Run detection
results = detect_greenongreen(image, params)
print(f"Found {len(results['detections'])} potential weeds")

# Visualize results
for detection in results['detections']:
    x1, y1, x2, y2 = detection['bbox']
    cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)

cv2.imshow("Green-on-Green Detection", image)
cv2.waitKey(0)
```

---

## Using Your Own Custom Model

### Overview

OWL supports TensorFlow Lite models for advanced machine learning-based weed detection. You can train your own custom model and integrate it into the system.

### 1. Model Requirements

**Supported Model Types:**
- **TensorFlow Lite (.tflite)**: Optimized for edge devices
- **Input Format**: RGB images, typically 224x224 or 416x416 pixels
- **Output Format**: Object detection with bounding boxes and confidence scores

**Expected Model Output:**
```python
# Model should output:
{
    'detection_boxes': [[y1, x1, y2, x2], ...],      # Normalized coordinates (0-1)
    'detection_classes': [1, 2, 1, ...],             # Class IDs
    'detection_scores': [0.95, 0.87, 0.76, ...],     # Confidence scores
    'num_detections': 3                               # Number of detections
}
```

### 2. Model Training Workflow

#### Data Collection
```python
# Use OWL's built-in image sampler to collect training data
from utils.image_sampler import ImageRecorder

recorder = ImageRecorder(
    save_directory="training_data",
    save_frequency=30,  # Save every 30 frames
    max_images=1000
)

# Run OWL with image recording enabled
# This creates a dataset of field images for labeling
```

#### Data Labeling
Use tools like:
- **LabelImg**: For bounding box annotation
- **CVAT**: Web-based annotation tool
- **Roboflow**: Commercial annotation platform

**Annotation Format**: COCO JSON or Pascal VOC XML

#### Model Training
```python
# Example training script using TensorFlow Object Detection API
import tensorflow as tf

# 1. Prepare dataset
train_dataset = create_dataset_from_annotations('training_data/')

# 2. Load pre-trained model (transfer learning)
base_model = tf.keras.applications.MobileNetV2(
    input_shape=(224, 224, 3),
    include_top=False,
    weights='imagenet'
)

# 3. Add detection head
model = tf.keras.Sequential([
    base_model,
    tf.keras.layers.GlobalAveragePooling2D(),
    tf.keras.layers.Dense(128, activation='relu'),
    tf.keras.layers.Dense(num_classes, activation='sigmoid')
])

# 4. Train model
model.compile(
    optimizer='adam',
    loss='binary_crossentropy',
    metrics=['accuracy']
)

model.fit(train_dataset, epochs=50, validation_data=val_dataset)

# 5. Convert to TensorFlow Lite
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()

# Save model
with open('custom_weed_model.tflite', 'wb') as f:
    f.write(tflite_model)
```

### 3. Model Integration

#### Step 1: Add Model Files

```bash
# Copy your trained model to the models directory
cp custom_weed_model.tflite models/
cp custom_labels.txt models/
```

#### Step 2: Update Configuration

Edit your config file:

```ini
[Targeting]
# Switch to machine learning algorithm
algorithm = ml

# Model configuration
model_path = models/custom_weed_model.tflite
model_labels = models/custom_labels.txt
model_input_size = 224
model_confidence_threshold = 0.5
model_nms_threshold = 0.4

# Detection zones (map image coordinates to nozzle zones)
nozzle_zones = 4
zone_width_pixels = 160  # For 640 pixel width / 4 zones
```

#### Step 3: Create Labels File

Create `models/custom_labels.txt`:
```
0 background
1 dandelion
2 crabgrass
3 plantain
4 clover
```

#### Step 4: Update Model Loader

The system automatically loads your custom model when `algorithm = ml` is set. The model loading happens in:

```python
# utils/ml_detection.py (you may need to create this)
class CustomMLDetector:
    def __init__(self, model_path, labels_path):
        # Load TensorFlow Lite model
        self.interpreter = tf.lite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        
        # Load labels
        with open(labels_path, 'r') as f:
            self.labels = [line.strip() for line in f.readlines()]
    
    def detect(self, image):
        # Preprocess image
        input_image = cv2.resize(image, (224, 224))
        input_image = input_image.astype(np.float32) / 255.0
        input_image = np.expand_dims(input_image, axis=0)
        
        # Run inference
        input_details = self.interpreter.get_input_details()
        output_details = self.interpreter.get_output_details()
        
        self.interpreter.set_tensor(input_details[0]['index'], input_image)
        self.interpreter.invoke()
        
        # Get outputs
        boxes = self.interpreter.get_tensor(output_details[0]['index'])[0]
        classes = self.interpreter.get_tensor(output_details[1]['index'])[0]
        scores = self.interpreter.get_tensor(output_details[2]['index'])[0]
        
        # Convert to OWL format
        detections = []
        for i in range(len(scores)):
            if scores[i] > self.confidence_threshold:
                y1, x1, y2, x2 = boxes[i]
                # Convert normalized coordinates to pixel coordinates
                h, w = image.shape[:2]
                x1, y1, x2, y2 = int(x1*w), int(y1*h), int(x2*w), int(y2*h)
                
                detections.append({
                    'bbox': [x1, y1, x2, y2],
                    'center': [(x1+x2)//2, (y1+y2)//2],
                    'confidence': float(scores[i]),
                    'class': self.labels[int(classes[i])],
                    'nozzle_zone': self.calculate_nozzle_zone((x1+x2)//2, w)
                })
        
        return {'detections': detections}
```

### 4. Model Performance Optimization

#### For Jetson Platforms:
```python
# Enable GPU acceleration
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.target_spec.supported_types = [tf.float16]  # Use FP16 for GPU
converter.experimental_new_converter = True
```

#### Model Quantization:
```python
# Post-training quantization for faster inference
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.representative_dataset = representative_data_gen
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type = tf.int8
converter.inference_output_type = tf.int8
```

### 5. Testing Custom Model

Create a test script:

```python
# test_custom_model.py
import cv2
from utils.ml_detection import CustomMLDetector

# Initialize detector
detector = CustomMLDetector(
    model_path='models/custom_weed_model.tflite',
    labels_path='models/custom_labels.txt'
)

# Test on image
image = cv2.imread('test_image.jpg')
results = detector.detect(image)

# Visualize results
for detection in results['detections']:
    x1, y1, x2, y2 = detection['bbox']
    confidence = detection['confidence']
    class_name = detection['class']
    
    # Draw bounding box
    cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
    
    # Add label
    label = f"{class_name}: {confidence:.2f}"
    cv2.putText(image, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

cv2.imshow("Custom Model Detection", image)
cv2.waitKey(0)
```

---

## Configuration System

### Configuration File Structure

OWL uses INI-format configuration files located in the `config/` directory:

```ini
[Camera]
# Camera settings
resolution_width = 640
resolution_height = 480
arducam_exposure = 4000
arducam_green_factor = 1.0
arducam_red_factor = 1.1
arducam_blue_factor = 1.25

[Targeting]
# Detection algorithm
algorithm = gog  # gob, gog, hsv, ml
confidence_threshold = 0.7
nms_threshold = 0.4

[Relays]
# Hardware control pins
pin_one = 7
pin_two = 11
pin_three = 13
pin_four = 15
activation_duration = 250  # milliseconds

[System]
# Performance settings
max_cpu_usage = 80
frame_rate_limit = 30
log_level = INFO
```

### Configuration Validation

The system validates all configuration parameters:

```python
# utils/config_manager.py
VALUE_VALIDATORS = {
    'arducam_exposure': ('int', 100, 20000),
    'resolution_width': ('int', 240, 1920),
    'resolution_height': ('int', 180, 1080),
    'confidence_threshold': ('float', 0.1, 1.0),
}
```

---

## GPIO and Hardware Control

### Output Control (Relays/Nozzles)

```python
class RelayController:
    def __init__(self, pin_one, pin_two, pin_three, pin_four):
        """Initialize GPIO pins for relay control"""
        import Jetson.GPIO as GPIO
        
        self.pins = [pin_one, pin_two, pin_three, pin_four]
        GPIO.setup(self.pins, GPIO.OUT, initial=GPIO.LOW)
    
    def activate_nozzle(self, nozzle_id, duration_ms):
        """Activate specific nozzle for specified duration"""
        if 0 <= nozzle_id < len(self.pins):
            GPIO.output(self.pins[nozzle_id], GPIO.HIGH)
            time.sleep(duration_ms / 1000.0)
            GPIO.output(self.pins[nozzle_id], GPIO.LOW)
```

### Input Control (Buttons/Switches)

```python
class UteController:
    def __init__(self):
        """Initialize input controls"""
        self.button_pins = [31, 33, 35, 37]  # Example pins
        
        for pin in self.button_pins:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    def check_inputs(self):
        """Check button states"""
        return {f'button_{i}': not GPIO.input(pin) 
                for i, pin in enumerate(self.button_pins)}
```

### Status Indicators (LEDs)

```python
class StatusIndicator:
    def __init__(self, green_pin, yellow_pin, red_pin):
        """Initialize status LED pins"""
        self.leds = {
            'green': green_pin,
            'yellow': yellow_pin, 
            'red': red_pin
        }
        
        for pin in self.leds.values():
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
    
    def show_status(self, status):
        """Display system status via LEDs"""
        # Turn off all LEDs
        for pin in self.leds.values():
            GPIO.output(pin, GPIO.LOW)
        
        # Turn on appropriate LED
        if status == 'ready':
            GPIO.output(self.leds['green'], GPIO.HIGH)
        elif status == 'detecting':
            GPIO.output(self.leds['yellow'], GPIO.HIGH)
        elif status == 'error':
            GPIO.output(self.leds['red'], GPIO.HIGH)
```

---

## Troubleshooting and Debugging

### Common Issues and Solutions

#### 1. Camera Issues

**Problem**: Camera not detected or black frames
```bash
# Check available cameras
ls /dev/video*

# Test camera directly
v4l2-ctl -d /dev/video0 --list-formats-ext

# Check OWL camera detection
python -c "from utils.video_manager import VideoStream; vs = VideoStream(); print(vs.CAMERA_VERSION)"
```

**Solution**: Verify camera connection, check permissions, ensure ArducamUtils is properly installed.

#### 2. Exposure Control Issues

**Problem**: Exposure not changing
```bash
# Test v4l2-ctl exposure control
v4l2-ctl -d /dev/video0 -C exposure
v4l2-ctl -d /dev/video0 -c exposure=4000
```

**Solution**: Use sensor register method (0x3012) for Arducam cameras, ensure continuous maintenance in update loop.

#### 3. GPIO Permission Issues

**Problem**: GPIO access denied
```bash
# Add user to gpio group
sudo usermod -a -G gpio $USER

# Check GPIO permissions
ls -la /dev/gpiomem
```

#### 4. Performance Issues

**Problem**: Low frame rate or high CPU usage
```python
# Enable performance monitoring
from utils.log_manager import LogManager
logger = LogManager.get_logger(__name__)

# Monitor processing times
start_time = time.time()
# ... processing code ...
processing_time = (time.time() - start_time) * 1000
logger.info(f"Processing time: {processing_time:.2f}ms")
```

**Solutions**:
- Reduce resolution in config
- Optimize detection algorithm parameters
- Use hardware acceleration (GPU) for ML models
- Enable Jetson performance modes

### Debugging Tools

#### 1. Enable Debug Logging

```ini
[System]
log_level = DEBUG
```

#### 2. Frame Capture for Analysis

```python
# Add to main loop for debugging
if frame_count % 100 == 0:  # Save every 100th frame
    cv2.imwrite(f"debug_frame_{frame_count}.jpg", image)
```

#### 3. Performance Profiling

```python
import cProfile
import pstats

# Profile the main detection function
profiler = cProfile.Profile()
profiler.enable()

# Run detection
results = detect_weeds(image)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative').print_stats(10)
```

#### 4. Real-time Monitoring

```python
# Add to main loop
detection_count = len(predictions['detections'])
fps = self.fps_counter.get_current_fps()
cpu_usage = psutil.cpu_percent()

self.logger.info(f"FPS: {fps:.1f}, Detections: {detection_count}, CPU: {cpu_usage:.1f}%")
```

---

## Performance Optimization Tips

### 1. Jetson-Specific Optimizations

```bash
# Enable maximum performance mode
sudo nvpmodel -m 0
sudo jetson_clocks

# Monitor system resources
jtop
```

### 2. Camera Optimization

```python
# Optimize camera parameters for performance
stream = VideoStream(
    src=0,
    resolution=(416, 320),  # Lower resolution for speed
    arducam_exposure=4000,
    # Minimize color processing if not needed
    arducam_brightness_alpha=1.0,
    arducam_brightness_beta=0
)
```

### 3. Algorithm Optimization

```python
# Use region of interest (ROI) to limit processing area
def detect_weeds_roi(image):
    height, width = image.shape[:2]
    
    # Only process center portion where weeds are likely
    roi_y1 = height // 4
    roi_y2 = 3 * height // 4
    roi = image[roi_y1:roi_y2, :]
    
    # Run detection on ROI
    results = detect_algorithm(roi)
    
    # Adjust coordinates back to full image
    for detection in results['detections']:
        detection['bbox'][1] += roi_y1  # Adjust y coordinates
        detection['bbox'][3] += roi_y1
        detection['center'][1] += roi_y1
    
    return results
```

---

This documentation provides a comprehensive overview of the OpenWeedLocator system. For specific implementation details or troubleshooting, refer to the individual source files and their inline documentation.