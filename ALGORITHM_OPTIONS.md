# OpenWeedLocator Algorithm Options

## Available Detection Algorithms

OpenWeedLocator supports the following detection algorithms:

### 1. **exhsv** (Current Default) ⭐
- **Description**: Enhanced HSV color space detection
- **Best for**: Brown soil backgrounds with green vegetation
- **Performance**: Fast, reliable
- **Use case**: Traditional farm fields with exposed soil

### 2. **gog** (Green-on-Green) 🌱
- **Description**: HSV-based detection optimized for green-on-green scenarios
- **Best for**: Dense crop fields where weeds grow among crops
- **Performance**: Moderate speed, good accuracy
- **Use case**: Mature crop fields, pastures, lawns

### 2b. **gog-ml** (Green-on-Green with ML) 🤖
- **Description**: YOLO-based detection with crop-specific trained models
- **Best for**: Precise weed species identification in specific crops
- **Performance**: Slower but highly accurate
- **Use case**: Professional farming with custom trained models
- **Requirements**: YOLO model files (.onnx format)

### 3. **exg** (Excess Green)
- **Description**: Classic ExG algorithm (Woebbecke et al. 1995)
- **Best for**: General vegetation detection
- **Performance**: Very fast
- **Use case**: Simple vegetation detection

### 4. **exgr** (Excess Green minus Excess Red)
- **Description**: ExG with red component subtraction
- **Best for**: Better soil/vegetation contrast
- **Performance**: Fast
- **Use case**: Fields with reddish soil

### 5. **maxg** (Maximum Green)
- **Description**: Maximum green algorithm (Jin et al. 2021)
- **Best for**: Vegetable plantations
- **Performance**: Fast
- **Use case**: Row crops, vegetable fields

### 6. **nexg** (Normalized ExG)
- **Description**: Normalized version of ExG
- **Best for**: Varying lighting conditions
- **Performance**: Fast
- **Use case**: Outdoor fields with changing light

### 7. **hsv** (HSV Threshold)
- **Description**: Pure HSV color space thresholding
- **Best for**: Controlled environments
- **Performance**: Very fast
- **Use case**: Greenhouse, indoor growing

### 8. **gndvi** (Green NDVI)
- **Description**: Green Normalized Difference Vegetation Index
- **Best for**: Vegetation health assessment
- **Performance**: Fast
- **Use case**: Precision agriculture monitoring

---

## How to Switch to Green-on-Green (gog)

### Step 1: Update Configuration File

Edit your config file (e.g., `config/DAY_SENSITIVITY_2.ini`):

```ini
# Change this line:
algorithm = exhsv

# To this:
algorithm = gog
```

### Step 2: Green-on-Green Parameters

The green-on-green section is already configured in your config file:

```ini
[GreenOnGreen]
# HSV thresholds for green vegetation
hue_min = 30          # Start of green hue range
hue_max = 85          # End of green hue range  
saturation_min = 40   # Minimum color saturation
saturation_max = 255  # Maximum color saturation
value_min = 40        # Minimum brightness
value_max = 255       # Maximum brightness

# Noise reduction
erode_iterations = 2  # Remove small noise
dilate_iterations = 2 # Fill gaps
blur_kernel = 5       # Smoothing

# Size filtering (pixels)
min_detection_area = 100   # Minimum weed size
max_detection_area = 5000  # Maximum weed size

# Detection threshold
confidence = 0.5      # Minimum confidence (0.0-1.0)
```

### Step 3: Parameter Tuning Guide

#### For Different Crop Types:

| Crop Type | Hue Range | Saturation | Value | Notes |
|-----------|-----------|------------|-------|-------|
| **Wheat** | 35-80 | 30-255 | 40-255 | Mature crops have yellow tint |
| **Corn** | 30-85 | 40-255 | 40-255 | Broad green spectrum |
| **Soybeans** | 35-75 | 45-255 | 40-255 | Darker green leaves |
| **Pasture** | 25-90 | 35-255 | 30-255 | Wide variety of grasses |

#### Tuning Process:

1. **Start with defaults** - Run the system and observe results
2. **Adjust hue range** - If missing green vegetation, widen hue range
3. **Adjust saturation** - If detecting brown/gray areas, increase saturation_min
4. **Adjust size filters** - Set min/max based on expected weed sizes
5. **Fine-tune confidence** - Lower for more sensitive detection

### Step 4: Test Your Settings

Run the system with display enabled to see detection results:

```bash
python owl.py --show-display
```

You should see:
- **Green mask overlay** showing detected vegetation
- **Bounding boxes** around detected weeds
- **Real-time parameter feedback** in the logs

---

## Switching Between Algorithms

### Quick Algorithm Test

You can quickly test different algorithms by editing the config file:

```ini
# Test different algorithms:
algorithm = exhsv    # Current default (brown soil)
algorithm = gog      # Green-on-green (dense vegetation)
algorithm = exg      # Simple green detection
algorithm = maxg     # Vegetable crops
```

### Algorithm Performance Comparison

| Algorithm | Speed | Accuracy | Best Use Case |
|-----------|-------|----------|---------------|
| **exhsv** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Brown soil backgrounds |
| **gog** | ⭐⭐⭐ | ⭐⭐⭐⭐ | Green crop fields |
| **exg** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | General vegetation |
| **maxg** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Vegetable plantations |
| **hsv** | ⭐⭐⭐⭐⭐ | ⭐⭐ | Simple thresholding |

---

## Troubleshooting Green-on-Green

### Common Issues:

#### 1. **Too Many False Positives**
- **Symptom**: Detecting crop plants as weeds
- **Solution**: Increase `saturation_min` and `min_detection_area`

#### 2. **Missing Weeds**
- **Symptom**: Not detecting obvious weeds
- **Solution**: Widen `hue_min`/`hue_max` range, lower `confidence`

#### 3. **Noisy Detections**
- **Symptom**: Many small scattered detections
- **Solution**: Increase `erode_iterations` and `min_detection_area`

#### 4. **Poor Performance**
- **Symptom**: Low frame rate
- **Solution**: Reduce image resolution, increase `min_detection_area`

### Debug Commands:

```bash
# Check current algorithm
grep "algorithm" config/DAY_SENSITIVITY_2.ini

# Test green-on-green specifically
python -c "
from utils.greenongreen_jetson import GreenOnGreenJetson
import configparser
config = configparser.ConfigParser()
config.read('config/DAY_SENSITIVITY_2.ini')
detector = GreenOnGreenJetson(config['GreenOnGreen'])
print('Green-on-Green detector initialized successfully')
"

# Test YOLO green-on-green
python test_yolo_gog.py

# Setup YOLOv8 for testing
python setup_yolo_test.py
```

### YOLO Green-on-Green Setup (gog-ml):

```bash
# 1. Download test model
python setup_yolo_test.py

# 2. Test implementation
python test_yolo_gog.py

# 3. Edit config file
# Set: algorithm = gog-ml
# Set crop_type in [GreenOnGreenML] section

# 4. Run system
python owl.py --show-display
```

---

## Fixed Issues for Jetson Nano

### ✅ **Coral AI Dependency Removed**
- **Problem**: Original green-on-green required Google Coral Edge TPU
- **Solution**: Created Jetson-compatible version using standard OpenCV

### ✅ **HSV-Based Detection**
- **Advantage**: Works on any hardware with OpenCV
- **Performance**: Optimized for Jetson Nano performance

### ✅ **Configuration Integration**
- **Benefit**: Fully integrated with OWL's config system
- **Validation**: All parameters are validated for correct ranges

### ✅ **Legacy Compatibility**
- **Maintained**: Works with existing OWL interface
- **Seamless**: Drop-in replacement for original implementation

---

## Next Steps

1. **Switch to Green-on-Green**: Edit config file to `algorithm = gog`
2. **Test in Field**: Run with `--show-display` to see results
3. **Tune Parameters**: Adjust HSV ranges based on your crop/weed types
4. **Optimize Performance**: Adjust detection areas and morphological operations

The green-on-green algorithm is now ready to use on your Jetson Nano! 🚀