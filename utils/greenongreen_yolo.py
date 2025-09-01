#!/usr/bin/env python3
"""
YOLO-based Green-on-Green detection for crop-specific weed identification
Supports multiple crop types with dedicated YOLO models (.pt format)
"""

import cv2
import numpy as np
import os
from pathlib import Path
from utils.log_manager import LogManager

# Try to import ultralytics for .pt model support
try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False

class GreenOnGreenYOLO:
    """YOLO-based green-on-green detection with crop-specific models"""
    
    def __init__(self, config_section):
        """Initialize with configuration parameters"""
        self.logger = LogManager.get_logger(__name__)
        
        # Model configuration
        self.crop_type = config_section.get('crop_type', fallback='general')
        self.model_directory = config_section.get('model_directory', fallback='models/yolo')
        self.confidence_threshold = config_section.getfloat('confidence_threshold', fallback=0.5)
        self.nms_threshold = config_section.getfloat('nms_threshold', fallback=0.4)
        self.input_size = config_section.getint('input_size', fallback=640)
        
        # Class filtering
        self.target_classes = self._parse_target_classes(config_section.get('target_classes', fallback=''))
        
        # Detection area filtering
        self.min_detection_area = config_section.getint('min_detection_area', fallback=100)
        self.max_detection_area = config_section.getint('max_detection_area', fallback=50000)
        
        # Model loading
        self.net = None
        self.class_names = []
        self.colors = []
        
        self._load_crop_model()
        
        self.logger.info(f"YOLO Green-on-Green initialized for crop: {self.crop_type}")
        self.logger.info(f"Model loaded: {self.model_path}")
        self.logger.info(f"Confidence threshold: {self.confidence_threshold}")
        self.logger.info(f"Target classes: {self.target_classes}")
    
    def _load_crop_model(self):
        """Load YOLO model based on crop type"""
        model_dir = Path(self.model_directory)
        
        # Define crop-specific model mappings (prefer .pt over .onnx)
        crop_models = {
            'wheat': ['yolo_wheat_weeds.pt', 'yolo_wheat_weeds.onnx'],
            'corn': ['yolo_corn_weeds.pt', 'yolo_corn_weeds.onnx'], 
            'soybean': ['yolo_soybean_weeds.pt', 'yolo_soybean_weeds.onnx'],
            'cotton': ['yolo_cotton_weeds.pt', 'yolo_cotton_weeds.onnx'],
            'general': ['yolo_general_weeds.pt', 'yolo_general_weeds.onnx'],
            'test': ['yolov8n.pt', 'yolov8n.onnx']  # For testing
        }
        
        # Get model filenames for crop type
        model_filenames = crop_models.get(self.crop_type.lower(), crop_models['general'])
        self.model_path = None
        
        # Try to find the model file (prefer .pt over .onnx)
        for model_filename in model_filenames:
            potential_path = model_dir / model_filename
            if potential_path.exists():
                self.model_path = potential_path
                break
        
        # Fallback to test model if crop-specific not found
        if self.model_path is None:
            self.logger.warning(f"Crop-specific model not found for {self.crop_type}")
            for model_filename in crop_models['test']:
                potential_path = model_dir / model_filename
                if potential_path.exists():
                    self.model_path = potential_path
                    self.logger.info(f"Using test model: {self.model_path}")
                    break
        
        # Check if model exists
        if self.model_path is None or not self.model_path.exists():
            raise FileNotFoundError(f"YOLO model not found. Tried: {model_filenames}")
        
        # Load YOLO model based on file extension
        try:
            if self.model_path.suffix.lower() == '.pt':
                # Load PyTorch model using ultralytics
                if not ULTRALYTICS_AVAILABLE:
                    raise ImportError("ultralytics package required for .pt models. Install with: pip install ultralytics")
                
                self.model = YOLO(str(self.model_path))
                self.use_ultralytics = True
                self.logger.info(f"PyTorch YOLO model loaded successfully: {self.model_path}")
                
            else:
                # Load ONNX model using OpenCV
                self.net = cv2.dnn.readNetFromONNX(str(self.model_path))
                
                # Set backend and target for optimization
                self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                
                # Try to use GPU if available
                try:
                    self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
                    self.logger.info("Using GPU acceleration for YOLO inference")
                except:
                    self.logger.info("Using CPU for YOLO inference")
                
                self.use_ultralytics = False
                self.logger.info(f"ONNX YOLO model loaded successfully: {self.model_path}")
            
        except Exception as e:
            raise RuntimeError(f"Failed to load YOLO model: {e}")
        
        # Load class names
        self._load_class_names()
        
        # Generate colors for visualization
        self._generate_colors()
    
    def _load_class_names(self):
        """Load class names for the model"""
        # Look for classes file next to model
        classes_file = self.model_path.parent / f"{self.model_path.stem}_classes.txt"
        
        # Fallback class files
        fallback_files = [
            self.model_path.parent / "classes.txt",
            self.model_path.parent / f"{self.crop_type}_classes.txt",
            self.model_path.parent / "coco_classes.txt"
        ]
        
        # Try to load classes
        for class_file in [classes_file] + fallback_files:
            if class_file.exists():
                try:
                    with open(class_file, 'r') as f:
                        self.class_names = [line.strip() for line in f.readlines()]
                    self.logger.info(f"Loaded {len(self.class_names)} classes from {class_file}")
                    return
                except Exception as e:
                    self.logger.warning(f"Failed to load classes from {class_file}: {e}")
        
        # Default classes if no file found
        self.class_names = [
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
        self.logger.warning(f"Using default COCO classes ({len(self.class_names)} classes)")
    
    def _parse_target_classes(self, target_classes_str):
        """Parse target classes from config string"""
        if not target_classes_str:
            return []  # Empty means detect all classes
        
        # Parse comma-separated class names or indices
        classes = []
        for item in target_classes_str.split(','):
            item = item.strip()
            if item.isdigit():
                classes.append(int(item))
            else:
                classes.append(item.lower())
        
        return classes
    
    def _generate_colors(self):
        """Generate random colors for each class"""
        np.random.seed(42)  # For consistent colors
        self.colors = np.random.randint(0, 255, size=(len(self.class_names), 3), dtype=np.uint8)
    
    def detect(self, image, **kwargs):
        """
        Detect weeds in the image using YOLO
        
        Args:
            image: BGR image from camera
            
        Returns:
            dict: Detection results in OWL format
        """
        try:
            if image is None or image.size == 0:
                return {'detections': [], 'total_detections': 0}
            
            if self.use_ultralytics:
                # Use ultralytics for .pt models
                detections = self._detect_with_ultralytics(image)
            else:
                # Use OpenCV for .onnx models
                detections = self._detect_with_opencv(image)
            
            return {
                'detections': detections,
                'total_detections': len(detections),
                'algorithm': 'yolo_green_on_green'
            }
            
        except Exception as e:
            self.logger.error(f"Error in YOLO detection: {e}")
            return {'detections': [], 'total_detections': 0}
    
    def _detect_with_ultralytics(self, image):
        """Detect using ultralytics YOLO (.pt models)"""
        try:
            # Run inference with ultralytics
            results = self.model(image, conf=self.confidence_threshold, verbose=False)
            
            detections = []
            image_height, image_width = image.shape[:2]
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        # Get box coordinates
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = float(box.conf[0].cpu().numpy())
                        class_id = int(box.cls[0].cpu().numpy())
                        
                        # Filter by target classes if specified
                        if self._should_include_class(class_id):
                            # Convert to integers
                            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                            width = x2 - x1
                            height = y2 - y1
                            
                            # Filter by area
                            area = width * height
                            if self.min_detection_area <= area <= self.max_detection_area:
                                # Calculate center and nozzle zone
                                center_x = x1 + width // 2
                                center_y = y1 + height // 2
                                nozzle_zone = self._calculate_nozzle_zone(center_x, image_width)
                                
                                # Get class name
                                class_name = self.class_names[class_id] if class_id < len(self.class_names) else f"class_{class_id}"
                                
                                detection = {
                                    'bbox': [x1, y1, x2, y2],
                                    'center': [center_x, center_y],
                                    'confidence': confidence,
                                    'class_id': class_id,
                                    'class_name': class_name,
                                    'area': area,
                                    'nozzle_zone': nozzle_zone
                                }
                                
                                detections.append(detection)
            
            # Sort by confidence (highest first)
            detections.sort(key=lambda x: x['confidence'], reverse=True)
            
            return detections
            
        except Exception as e:
            self.logger.error(f"Error in ultralytics detection: {e}")
            return []
    
    def _detect_with_opencv(self, image):
        """Detect using OpenCV DNN (.onnx models)"""
        try:
            # Prepare input blob
            blob = cv2.dnn.blobFromImage(image, 1/255.0, (self.input_size, self.input_size), 
                                       swapRB=True, crop=False)
            
            # Set input to the network
            self.net.setInput(blob)
            
            # Run inference
            outputs = self.net.forward()
            
            # Process outputs
            return self._process_outputs(outputs, image.shape)
            
        except Exception as e:
            self.logger.error(f"Error in OpenCV detection: {e}")
            return []
    
    def _process_outputs(self, outputs, image_shape):
        """Process YOLO outputs and convert to OWL format"""
        detections = []
        image_height, image_width = image_shape[:2]
        
        # Parse YOLO outputs
        boxes = []
        confidences = []
        class_ids = []
        
        for output in outputs:
            for detection in output:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                
                if confidence > self.confidence_threshold:
                    # Filter by target classes if specified
                    if self._should_include_class(class_id):
                        # Scale coordinates to image size
                        center_x = int(detection[0] * image_width)
                        center_y = int(detection[1] * image_height)
                        width = int(detection[2] * image_width)
                        height = int(detection[3] * image_height)
                        
                        # Calculate top-left corner
                        x = int(center_x - width / 2)
                        y = int(center_y - height / 2)
                        
                        boxes.append([x, y, width, height])
                        confidences.append(float(confidence))
                        class_ids.append(class_id)
        
        # Apply Non-Maximum Suppression
        if len(boxes) > 0:
            indices = cv2.dnn.NMSBoxes(boxes, confidences, 
                                     self.confidence_threshold, self.nms_threshold)
            
            if len(indices) > 0:
                for i in indices.flatten():
                    x, y, width, height = boxes[i]
                    confidence = confidences[i]
                    class_id = class_ids[i]
                    
                    # Filter by area
                    area = width * height
                    if self.min_detection_area <= area <= self.max_detection_area:
                        # Calculate center and nozzle zone
                        center_x = x + width // 2
                        center_y = y + height // 2
                        nozzle_zone = self._calculate_nozzle_zone(center_x, image_width)
                        
                        # Get class name
                        class_name = self.class_names[class_id] if class_id < len(self.class_names) else f"class_{class_id}"
                        
                        detection = {
                            'bbox': [x, y, x + width, y + height],
                            'center': [center_x, center_y],
                            'confidence': confidence,
                            'class_id': class_id,
                            'class_name': class_name,
                            'area': area,
                            'nozzle_zone': nozzle_zone
                        }
                        
                        detections.append(detection)
        
        # Sort by confidence (highest first)
        detections.sort(key=lambda x: x['confidence'], reverse=True)
        
        return detections
    
    def _should_include_class(self, class_id):
        """Check if class should be included based on target_classes filter"""
        if not self.target_classes:
            return True  # Include all classes if no filter specified
        
        # Check by class ID
        if class_id in self.target_classes:
            return True
        
        # Check by class name
        if class_id < len(self.class_names):
            class_name = self.class_names[class_id].lower()
            if class_name in self.target_classes:
                return True
        
        return False
    
    def _calculate_nozzle_zone(self, center_x, image_width, num_zones=4):
        """Calculate which nozzle zone a detection belongs to"""
        zone_width = image_width / num_zones
        zone = int(center_x / zone_width)
        return min(max(zone, 0), num_zones - 1)
    
    def visualize_detections(self, image, detections):
        """Draw bounding boxes and labels on image"""
        vis_image = image.copy()
        
        for detection in detections:
            x1, y1, x2, y2 = detection['bbox']
            confidence = detection['confidence']
            class_name = detection['class_name']
            class_id = detection['class_id']
            
            # Get color for this class
            color = self.colors[class_id % len(self.colors)].tolist()
            
            # Draw bounding box
            cv2.rectangle(vis_image, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            label = f"{class_name}: {confidence:.2f}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
            
            # Draw label background
            cv2.rectangle(vis_image, (x1, y1 - label_size[1] - 10), 
                         (x1 + label_size[0], y1), color, -1)
            
            # Draw label text
            cv2.putText(vis_image, label, (x1, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return vis_image
    
    def update_parameters(self, **kwargs):
        """Update detection parameters at runtime"""
        for param, value in kwargs.items():
            if hasattr(self, param):
                setattr(self, param, value)
                self.logger.info(f"Updated {param} to {value}")


def detect_greenongreen_yolo(image, config_section):
    """
    Standalone function for YOLO-based green-on-green detection
    Compatible with existing OWL algorithm interface
    
    Args:
        image: BGR image
        config_section: Configuration section with parameters
        
    Returns:
        tuple: (visualization_image, detections_dict, is_binary_mask)
    """
    detector = GreenOnGreenYOLO(config_section)
    results = detector.detect(image)
    
    # Create visualization image
    vis_image = detector.visualize_detections(image, results['detections'])
    
    return vis_image, results, False  # False indicates this is not a binary mask