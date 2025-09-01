#!/usr/bin/env python3
"""
Debug script to test exposure setting from config
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.video_manager import VideoStream
from utils.log_manager import LogManager
from configparser import ConfigParser

def test_exposure_from_config():
    """Test if exposure from config is being applied"""
    
    # Load config file
    config = ConfigParser()
    config.read('config/DAY_SENSITIVITY_2.ini')
    
    # Get exposure value from config
    config_exposure = config.getint('Camera', 'arducam_exposure', fallback=4000)
    print(f"📋 Config file exposure: {config_exposure}")
    
    # Test different exposure values
    test_exposures = [config_exposure, 6000, 2000]
    
    for test_exp in test_exposures:
        print(f"\n🧪 Testing exposure: {test_exp}")
        
        try:
            # Initialize camera with specific exposure
            camera = VideoStream(resolution=(640, 480), exposure=test_exp)
            camera.start()
            
            print(f"✅ Camera initialized: {camera.CAMERA_VERSION}")
            
            if camera.CAMERA_VERSION == 'arducam':
                # Check if exposure was set
                actual_exposure = camera.get_exposure()
                print(f"📖 Actual sensor exposure: {actual_exposure}")
                
                if actual_exposure is not None:
                    if abs(actual_exposure - test_exp) < 100:  # Allow some tolerance
                        print(f"✅ Exposure set correctly!")
                    else:
                        print(f"⚠️  Exposure mismatch: expected {test_exp}, got {actual_exposure}")
                else:
                    print(f"❌ Could not read exposure from sensor")
                    
                # Try setting a new exposure
                new_exp = test_exp + 1000
                print(f"🔧 Trying to set new exposure: {new_exp}")
                if camera.set_exposure(new_exp):
                    # Read it back
                    readback_exp = camera.get_exposure()
                    print(f"📖 Readback exposure: {readback_exp}")
                else:
                    print(f"❌ Failed to set new exposure")
            else:
                print(f"⚠️  Not using ArducamStream, using {camera.CAMERA_VERSION}")
            
            camera.stop()
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
        
        print("-" * 50)

if __name__ == "__main__":
    print("🔍 Arducam Exposure Debug Test")
    print("=" * 50)
    test_exposure_from_config()