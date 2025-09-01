# YOLO Models for Green-on-Green Detection

This directory contains YOLO models for crop-specific weed detection.

## Model Files

Place your YOLO models (.pt or .onnx format) in this directory:

### Supported Formats
- **.pt** - PyTorch format (preferred, better performance)
- **.onnx** - ONNX format (fallback option)

### Crop-Specific Models
- `yolo_wheat_weeds.pt` / `yolo_wheat_weeds.onnx` - Wheat field weed detection
- `yolo_corn_weeds.pt` / `yolo_corn_weeds.onnx` - Corn field weed detection  
- `yolo_soybean_weeds.pt` / `yolo_soybean_weeds.onnx` - Soybean field weed detection
- `yolo_cotton_weeds.pt` / `yolo_cotton_weeds.onnx` - Cotton field weed detection
- `yolo_general_weeds.pt` / `yolo_general_weeds.onnx` - General crop weed detection

### Test Model
- `yolov8n.pt` / `yolov8n.onnx` - YOLOv8 nano for testing (detects general objects)

## Class Files

For each model, create a corresponding classes file:
- `yolo_wheat_weeds_classes.txt`
- `yolo_corn_weeds_classes.txt`
- etc.

Or use a generic `classes.txt` file.

## How to Get YOLOv8 for Testing

### Option 1: Download .pt Model (Recommended)
```bash
# Install ultralytics
pip install ultralytics

# Download YOLOv8n .pt model
python3 setup_yolo_pt.py
```

### Option 2: Download .onnx Model
```bash
# Install ultralytics
pip install ultralytics

# Download and convert YOLOv8n to ONNX
python3 -c "
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
model.export(format='onnx')
"

# Move to models directory
mv yolov8n.onnx models/yolo/
```

## Configuration

Set your crop type in the config file:

```ini
[GreenOnGreenML]
crop_type = test  # Uses yolov8n.onnx for testing
# or
crop_type = wheat  # Uses yolo_wheat_weeds.onnx
```

## Class Names

Create a classes file for your model. For YOLOv8 (COCO dataset), use:

```
person
bicycle
car
motorcycle
airplane
bus
train
truck
boat
traffic light
...
```

Or the system will use default COCO classes.