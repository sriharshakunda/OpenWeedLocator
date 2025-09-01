#!/usr/bin/env python3
"""
Test script for YOLO-based Green-on-Green detection
"""

import sys
import os
import configparser
sys.path.insert(0, '/home/ubuntu/OpenWeedLocator')

import cv2
import numpy as np

def test_yolo_gog():
    """Test the YOLO green-on-green implementation"""
    print("Testing YOLO Green-on-Green implementation...")
    
    try:
        # Load config
        config = configparser.ConfigParser()
        config.read('config/DAY_SENSITIVITY_2.ini')
        
        print(f"Crop type: {config.get('GreenOnGreenML', 'crop_type')}")
        print(f"Model directory: {config.get('GreenOnGreenML', 'model_directory')}")
        
        # Test initialization
        from utils.greenongreen_yolo import GreenOnGreenYOLO
        
        detector = GreenOnGreenYOLO(config['GreenOnGreenML'])
        print("✅ YOLO detector initialized successfully")
        
        # Create a test image
        test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        # Test detection
        results = detector.detect(test_image)
        print(f"✅ Detection test completed")
        print(f"Detections found: {results['total_detections']}")
        print(f"Algorithm: {results['algorithm']}")
        
        # Test visualization
        if results['detections']:
            vis_image = detector.visualize_detections(test_image, results['detections'])
            print("✅ Visualization test completed")
        else:
            print("✅ No detections to visualize (expected with random image)")
        
        print("\n🎉 All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_integration():
    """Test config integration and validation"""
    print("\nTesting configuration integration...")
    
    try:
        from utils.config_manager import ConfigManager
        
        # Test config validation
        config_manager = ConfigManager()
        is_valid = config_manager.validate_config('config/DAY_SENSITIVITY_2.ini')
        
        if is_valid:
            print("✅ Configuration validation passed")
        else:
            print("❌ Configuration validation failed")
            return False
            
        # Check algorithm validity
        config = configparser.ConfigParser()
        config.read('config/DAY_SENSITIVITY_2.ini')
        
        # Test gog-ml algorithm
        test_config = config.copy()
        test_config.set('', 'algorithm', 'gog-ml')
        
        algorithm = test_config.get('', 'algorithm')
        if algorithm in config_manager.VALID_ALGORITHMS:
            print(f"✅ Algorithm '{algorithm}' is valid")
        else:
            print(f"❌ Algorithm '{algorithm}' is not valid")
            return False
            
        print("✅ Config integration test passed")
        return True
        
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        return False

def show_crop_models():
    """Show available crop model mappings"""
    print("\nAvailable crop types and models:")
    
    crop_models = {
        'wheat': 'yolo_wheat_weeds.onnx',
        'corn': 'yolo_corn_weeds.onnx', 
        'soybean': 'yolo_soybean_weeds.onnx',
        'cotton': 'yolo_cotton_weeds.onnx',
        'general': 'yolo_general_weeds.onnx',
        'test': 'yolov8n.onnx'
    }
    
    for crop, model in crop_models.items():
        model_path = f"models/yolo/{model}"
        exists = "✅" if os.path.exists(model_path) else "❌"
        print(f"  {crop:10} → {model:25} {exists}")
    
    print("\nTo use a specific crop:")
    print("1. Edit config/DAY_SENSITIVITY_2.ini")
    print("2. Set: algorithm = gog-ml")
    print("3. Set: crop_type = wheat  (or corn, soybean, etc.)")
    print("4. Ensure the corresponding model file exists in models/yolo/")

if __name__ == "__main__":
    print("YOLO Green-on-Green Test Suite")
    print("=" * 50)
    
    success = True
    
    # Run tests
    success &= test_config_integration()
    success &= test_yolo_gog()
    
    # Show model info
    show_crop_models()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests passed! YOLO Green-on-Green is ready to use.")
        print("\nNext steps:")
        print("1. Download a YOLO model (see models/yolo/README.md)")
        print("2. Set algorithm = gog-ml in your config file")
        print("3. Set your crop_type in [GreenOnGreenML] section") 
        print("4. Run: python owl.py --show-display")
    else:
        print("❌ Some tests failed. Check the output above.")