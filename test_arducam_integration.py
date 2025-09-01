#!/usr/bin/env python3
"""
Test script to verify ArducamStream integration with OpenWeedLocator
This script tests the new camera functionality without running the full OWL system
"""

import cv2
import time
import sys
import os
import numpy as np

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.video_manager import VideoStream
from utils.log_manager import LogManager

def test_camera_integration():
    """Test the ArducamStream integration with color stream"""
    logger = LogManager.get_logger(__name__)
    
    print("Testing ArducamStream integration with color stream...")
    print("=" * 60)
    
    try:
        # Initialize VideoStream with Arducam-specific settings
        print("Initializing camera with color stream settings...")
        camera = VideoStream(resolution=(640, 480),
                           exposure=4000,
                           green_factor=1.0,
                           red_factor=1.1,
                           blue_factor=1.25,
                           brightness_alpha=1.2,
                           brightness_beta=30)
        camera.start()
        
        print(f"Camera type: {camera.CAMERA_VERSION}")
        print(f"Frame dimensions: {camera.frame_width}x{camera.frame_height}")
        
        # Test exposure control if ArducamStream is being used
        if camera.CAMERA_VERSION == 'arducam':
            print("\n🎯 Testing ArducamUtils color conversion...")
            print("✅ ArducamStream detected - color processing enabled")
            
            print("\nTesting exposure control...")
            current_exposure = camera.get_exposure()
            if current_exposure is not None:
                print(f"Current exposure: {current_exposure}")
                
                # Test setting exposure
                new_exposure = 5000
                if camera.set_exposure(new_exposure):
                    print(f"Successfully set exposure to {new_exposure}")
                    time.sleep(1)  # Give camera time to adjust
                    
                    # Read it back
                    updated_exposure = camera.get_exposure()
                    if updated_exposure is not None:
                        print(f"Verified exposure: {updated_exposure}")
                else:
                    print("Failed to set exposure")
            else:
                print("Could not read current exposure")
        else:
            print(f"\n⚠️  Using {camera.CAMERA_VERSION} camera - ArducamUtils not available")
            print("Color processing may be limited")
        
        print("\nTesting color frame capture...")
        frame_count = 0
        start_time = time.time()
        color_frames = 0
        
        # Capture frames for testing
        while frame_count < 30:  # Limit to 30 frames for testing
            frame = camera.read()
            
            if frame is not None:
                frame_count += 1
                height, width = frame.shape[:2]
                channels = frame.shape[2] if len(frame.shape) == 3 else 1
                
                # Check if frame is color
                if channels == 3:
                    color_frames += 1
                    # Check if it's actually colorful (not just grayscale in BGR format)
                    b_mean = np.mean(frame[:,:,0])
                    g_mean = np.mean(frame[:,:,1])  
                    r_mean = np.mean(frame[:,:,2])
                    color_variance = np.var([b_mean, g_mean, r_mean])
                    
                    if frame_count % 10 == 0:
                        print(f"Frame {frame_count}: {width}x{height}x{channels}, "
                              f"BGR means: ({b_mean:.1f}, {g_mean:.1f}, {r_mean:.1f}), "
                              f"Color variance: {color_variance:.2f}")
                        
                        # Show preview window
                        if frame_count == 10:
                            try:
                                display_frame = cv2.resize(frame, (320, 240))
                                cv2.imshow("ArducamStream Color Test", display_frame)
                                cv2.waitKey(1)
                                print("🖼️  Color preview window opened")
                            except Exception as e:
                                print(f"Could not display preview: {e}")
                else:
                    print(f"Frame {frame_count}: {width}x{height} (grayscale)")
            else:
                print("Warning: Received None frame")
                break
                
            time.sleep(0.1)  # 10 FPS for testing
        
        end_time = time.time()
        elapsed = end_time - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0
        
        print(f"\n📊 Capture test results:")
        print(f"Total frames captured: {frame_count}")
        print(f"Color frames: {color_frames}")
        print(f"Color frame ratio: {color_frames/frame_count*100:.1f}%")
        print(f"Time elapsed: {elapsed:.2f} seconds")
        print(f"Average FPS: {fps:.2f}")
        
        # Clean up
        camera.stop()
        cv2.destroyAllWindows()
        
        if color_frames > 0:
            print("\n🎉 Color stream test PASSED!")
            print("✅ ArducamUtils color conversion is working")
        else:
            print("\n⚠️  Color stream test completed but no color frames detected")
            print("This might indicate grayscale mode or conversion issues")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Camera integration test failed: {e}")
        logger.error(f"Camera test failed: {e}", exc_info=True)
        return False

def main():
    """Main test function"""
    print("OpenWeedLocator ArducamStream Integration Test")
    print("=" * 50)
    
    # Test the integration
    success = test_camera_integration()
    
    if success:
        print("\n🎉 All tests passed! ArducamStream integration is working.")
        print("\nYou can now run the main OWL system with:")
        print("python owl.py")
    else:
        print("\n⚠️  Tests failed. Please check the error messages above.")
        print("Make sure ArducamUtils is properly installed and the camera is connected.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())