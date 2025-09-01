#!/usr/bin/env python3
"""
Setup script to download YOLOv8 .pt model for testing YOLO Green-on-Green
"""

import os
import sys
from pathlib import Path

def setup_yolo_pt():
    """Download and setup YOLOv8 .pt model for testing"""
    print("Setting up YOLOv8 .pt model for testing...")
    
    # Check if models directory exists
    models_dir = Path("models/yolo")
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if YOLOv8 .pt model already exists
    model_path = models_dir / "yolov8n.pt"
    if model_path.exists():
        print(f"✅ YOLOv8 .pt model already exists: {model_path}")
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
        
        # Download YOLOv8 nano model
        print("Downloading YOLOv8 nano .pt model...")
        from ultralytics import YOLO
        
        # Load YOLOv8 nano model (will download if not present)
        model = YOLO('yolov8n.pt')
        print("✅ YOLOv8 .pt model downloaded")
        
        # Copy to models directory
        import shutil
        source_path = Path("yolov8n.pt")
        if source_path.exists():
            shutil.copy2(source_path, model_path)
            print(f"✅ Model copied to: {model_path}")
        else:
            print("❌ .pt file not found after download")
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
        
        print("\n🎉 YOLOv8 .pt setup completed successfully!")
        print(f"Model location: {model_path}")
        print(f"Classes file: {classes_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_config_for_pt():
    """Update config file to use YOLO .pt model"""
    print("\nUpdating config for YOLO .pt model...")
    
    try:
        import configparser
        
        config_file = "config/DAY_SENSITIVITY_2.ini"
        config = configparser.ConfigParser()
        config.read(config_file)
        
        # Update algorithm
        config.set('System', 'algorithm', 'gog-ml')
        print("✅ Set algorithm = gog-ml")
        
        # Update crop type
        config.set('GreenOnGreenML', 'crop_type', 'test')
        print("✅ Set crop_type = test")
        
        # Update target classes for testing
        config.set('GreenOnGreenML', 'target_classes', '0')
        print("✅ Set target_classes = 0 (person)")
        
        # Save config
        with open(config_file, 'w') as f:
            config.write(f)
        
        print(f"✅ Config updated: {config_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Config update failed: {e}")
        return False

if __name__ == "__main__":
    print("YOLOv8 .pt Setup for Green-on-Green Testing")
    print("=" * 50)
    
    success = setup_yolo_pt()
    
    if success:
        update_config_for_pt()
        
        print("\n" + "=" * 50)
        print("🎉 Setup complete! You can now test YOLO .pt Green-on-Green:")
        print()
        print("1. Test the implementation:")
        print("   python3 test_yolo_gog.py")
        print()
        print("2. Run the main system:")
        print("   python3 owl.py --show-display")
        print()
        print("3. The system will use YOLOv8 .pt to detect persons")
        print("   (class 0 - good for testing)")
        print()
        print("4. To detect other classes, edit config file:")
        print("   target_classes = 0,2,5  # person, car, bus")
        print()
        print("5. Later, replace with your custom weed detection .pt model")
    else:
        print("\n❌ Setup failed. Check the errors above.") 