#!/usr/bin/env python3
"""
Green-on-Green detection for Jetson Nano without Coral AI dependency
Uses standard computer vision techniques for vegetation detection
"""

import cv2
import numpy as np
from utils.log_manager import LogManager

class GreenOnGreenJetson:
    """Green-on-green detection using HSV color space and morphological operations"""
    
    def __init__(self, config_section):
        """Initialize with configuration parameters"""
        self.logger = LogManager.get_logger(__name__)
        
        # HSV thresholds for green vegetation
        self.hue_min = config_section.getint('hue_min', fallback=30)
        self.hue_max = config_section.getint('hue_max', fallback=85)
        self.saturation_min = config_section.getint('saturation_min', fallback=40)
        self.saturation_max = config_section.getint('saturation_max', fallback=255)
        self.value_min = config_section.getint('value_min', fallback=40)
        self.value_max = config_section.getint('value_max', fallback=255)
        
        # Morphological operation parameters
        self.erode_iterations = config_section.getint('erode_iterations', fallback=2)
        self.dilate_iterations = config_section.getint('dilate_iterations', fallback=2)
        self.blur_kernel = config_section.getint('blur_kernel', fallback=5)
        
        # Size filtering
        self.min_detection_area = config_section.getint('min_detection_area', fallback=100)
        self.max_detection_area = config_section.getint('max_detection_area', fallback=5000)
        
        # Confidence threshold
        self.confidence_threshold = config_section.getfloat('confidence', fallback=0.5)
        
        self.logger.info(f"Green-on-Green Jetson initialized with HSV range: H({self.hue_min}-{self.hue_max}), "
                        f"S({self.saturation_min}-{self.saturation_max}), V({self.value_min}-{self.value_max})")
    
    def detect(self, image, **kwargs):
        """
        Detect green vegetation in the image
        
        Args:
            image: BGR image from camera
            
        Returns:
            dict: Detection results in OWL format
        """
        try:
            if image is None or image.size == 0:
                return {'detections': [], 'total_detections': 0}
            
            # Convert BGR to HSV
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # Create mask for green vegetation
            lower_green = np.array([self.hue_min, self.saturation_min, self.value_min])
            upper_green = np.array([self.hue_max, self.saturation_max, self.value_max])
            
            green_mask = cv2.inRange(hsv, lower_green, upper_green)
            
            # Apply morphological operations to reduce noise
            if self.blur_kernel > 1:
                green_mask = cv2.medianBlur(green_mask, self.blur_kernel)
            
            # Morphological operations
            if self.erode_iterations > 0:
                kernel_erode = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                green_mask = cv2.erode(green_mask, kernel_erode, iterations=self.erode_iterations)
            
            if self.dilate_iterations > 0:
                kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                green_mask = cv2.dilate(green_mask, kernel_dilate, iterations=self.dilate_iterations)
            
            # Find contours
            contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Process contours and create detections
            detections = []
            image_height, image_width = image.shape[:2]
            
            for contour in contours:
                area = cv2.contourArea(contour)
                
                # Filter by area
                if self.min_detection_area <= area <= self.max_detection_area:
                    # Get bounding rectangle
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    # Calculate center point
                    center_x = x + w // 2
                    center_y = y + h // 2
                    
                    # Calculate confidence based on area and shape
                    confidence = min(area / self.max_detection_area, 1.0)
                    
                    # Apply confidence threshold
                    if confidence >= self.confidence_threshold:
                        # Determine which nozzle zone this detection belongs to
                        nozzle_zone = self._calculate_nozzle_zone(center_x, image_width)
                        
                        detection = {
                            'bbox': [x, y, x + w, y + h],
                            'center': [center_x, center_y],
                            'confidence': float(confidence),
                            'area': int(area),
                            'nozzle_zone': nozzle_zone
                        }
                        
                        detections.append(detection)
            
            # Sort detections by confidence (highest first)
            detections.sort(key=lambda x: x['confidence'], reverse=True)
            
            return {
                'detections': detections,
                'total_detections': len(detections),
                'algorithm': 'green_on_green_jetson'
            }
            
        except Exception as e:
            self.logger.error(f"Error in green-on-green detection: {e}")
            return {'detections': [], 'total_detections': 0}
    
    def _calculate_nozzle_zone(self, center_x, image_width, num_zones=4):
        """Calculate which nozzle zone a detection belongs to"""
        zone_width = image_width / num_zones
        zone = int(center_x / zone_width)
        return min(max(zone, 0), num_zones - 1)  # Clamp to valid range
    
    def update_parameters(self, **kwargs):
        """Update detection parameters at runtime"""
        for param, value in kwargs.items():
            if hasattr(self, param):
                setattr(self, param, value)
                self.logger.info(f"Updated {param} to {value}")


def detect_greenongreen_hsv(image, config_section):
    """
    Standalone function for green-on-green detection using HSV thresholding
    Compatible with existing OWL algorithm interface
    
    Args:
        image: BGR image
        config_section: Configuration section with parameters
        
    Returns:
        tuple: (processed_image, detections_dict, is_binary_mask)
    """
    detector = GreenOnGreenJetson(config_section)
    results = detector.detect(image)
    
    # Create visualization mask for display
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_green = np.array([detector.hue_min, detector.saturation_min, detector.value_min])
    upper_green = np.array([detector.hue_max, detector.saturation_max, detector.value_max])
    mask = cv2.inRange(hsv, lower_green, upper_green)
    
    # Apply same morphological operations as detection
    if detector.blur_kernel > 1:
        mask = cv2.medianBlur(mask, detector.blur_kernel)
    
    if detector.erode_iterations > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.erode(mask, kernel, iterations=detector.erode_iterations)
    
    if detector.dilate_iterations > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.dilate(mask, kernel, iterations=detector.dilate_iterations)
    
    return mask, results, True  # True indicates this is a binary mask


# Compatibility function for existing code
def GreenOnGreen_test(image, config_section):
    """Compatibility wrapper for existing green-on-green calls"""
    return detect_greenongreen_hsv(image, config_section)