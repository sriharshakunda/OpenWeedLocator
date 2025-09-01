#!/usr/bin/env python3
"""
Setup script to download YOLOv8 for testing YOLO Green-on-Green
"""

import os
import sys
from pathlib import Path

def setup_yolo_test():
    """Download and setup YOLOv8 for testing"""
    print("Setting up YOLOv8 for testing...")
    
    # Check if models directory exists
    models_dir = Path("models/yolo")
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if YOLOv8 model already exists
    model_path = models_dir / "yolov8n.onnx"
    if model_path.exists():
        print(f"✅ YOLOv8 model already exists: {model_path}")
        return True
    
    try:
        # Try to install ultralytics if not available
        try:
            import ultralytics
            print("✅ Ultralytics already installed")
        except ImportError:
            print("Installing ultralytics...")
            import subprocess
            result = subprocess.run([sys.executable, "-m", "pip", "install", "ultralytics"], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ Failed to install ultralytics: {result.stderr}")
                return False
            print("✅ Ultralytics installed successfully")
        
        # Download and convert YOLOv8
        print("Downloading YOLOv8 nano model...")
        from ultralytics import YOLO
        
        # Load YOLOv8 nano model (will download if not present)
        model = YOLO('yolov8n.pt')
        print("✅ YOLOv8 model downloaded")
        
        # Export to ONNX format
        print("Converting to ONNX format...")
        model.export(format='onnx', imgsz=640, dynamic=False)
        
        # Move to models directory
        source_path = Path("yolov8n.onnx")
        if source_path.exists():
            source_path.rename(model_path)
            print(f"✅ Model moved to: {model_path}")
        else:
            print("❌ ONNX file not found after export")
            return False
        
        # Create classes file
        classes_file = models_dir / "yolov8n_classes.txt"
        coco_classes = [
            'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
            'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat',
            'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack',
            'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
            'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
            'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
            'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake',
            'chair', 'couch', 'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop',
            'mouse', 'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink',
            'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier',
            'toothbrush'
        ]
        
        with open(classes_file, 'w') as f:
            for class_name in coco_classes:
                f.write(f"{class_name}\n")
        
        print(f"✅ Classes file created: {classes_file}")
        
        print("\n🎉 YOLOv8 setup completed successfully!")
        print(f"Model location: {model_path}")
        print(f"Classes file: {classes_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_config_for_test():
    """Update config file to use YOLO test mode"""
    print("\nUpdating config for YOLO test...")
    
    try:
        import configparser
        
        config_file = "config/DAY_SENSITIVITY_2.ini"
        config = configparser.ConfigParser()
        config.read(config_file)
        
        # Update algorithm
        config.set('', 'algorithm', 'gog-ml')
        print("✅ Set algorithm = gog-ml")
        
        # Update crop type
        config.set('GreenOnGreenML', 'crop_type', 'test')
        print("✅ Set crop_type = test")
        
        # Save config
        with open(config_file, 'w') as f:
            config.write(f)
        
        print(f"✅ Config updated: {config_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Config update failed: {e}")
        return False

if __name__ == "__main__":
    print("YOLOv8 Setup for Green-on-Green Testing")
    print("=" * 50)
    
    success = setup_yolo_test()
    
    if success:
        update_config_for_test()
        
        print("\n" + "=" * 50)
        print("🎉 Setup complete! You can now test YOLO Green-on-Green:")
        print()
        print("1. Test the implementation:")
        print("   python test_yolo_gog.py")
        print()
        print("2. Run the main system:")
        print("   python owl.py --show-display")
        print()
        print("3. The system will use YOLOv8 to detect objects")
        print("   (people, cars, etc. - good for testing)")
        print()
        print("4. Later, replace with your custom weed detection model")
    else:
        print("\n❌ Setup failed. Check the errors above.")