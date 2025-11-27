#!/usr/bin/env python3
"""
ROS2 Node for detecting 'like' gesture using YOLOv8 ONNX model
Uses ONNX Runtime directly - no Roboflow inference library needed
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
from ament_index_python.packages import get_package_share_directory
import os
import cv2
import numpy as np
import onnxruntime as ort
import yaml

class LikeDetectorNode(Node):
    def __init__(self):
        super().__init__('pipeline_ros_bridge')
        
        # 1. ROS 2 Publisher
        self.publisher_ = self.create_publisher(Bool, '/like_detected', 10)
        self.get_logger().info("✅ ROS 2 Publisher for /like_detected is ready.")
        
        # 2. Get model paths
        pkg_share_dir = get_package_share_directory('yolo_like_detector')
        self.model_path = os.path.join(pkg_share_dir, 'weights', 'best.onnx')
        self.yaml_path = os.path.join(pkg_share_dir, 'weights', 'data.yaml')
        
        # Check if files exist
        if not os.path.exists(self.model_path):
            self.get_logger().error(f"❌ ONNX model not found: {self.model_path}")
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        
        self.get_logger().info(f"📦 Loading ONNX model: {self.model_path}")
        
        # 3. Load class names from data.yaml
        self.class_names = self.load_class_names()
        self.get_logger().info(f"📋 Classes loaded: {self.class_names}")
        
        # 4. Initialize ONNX Runtime session
        self.session = ort.InferenceSession(self.model_path)
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        self.output_names = [out.name for out in self.session.get_outputs()]
        
        self.get_logger().info(f"🔧 Model input: {self.input_name}, shape: {self.input_shape}")
        self.get_logger().info(f"🔧 Model outputs: {self.output_names}")
        
        # 5. Get input dimensions
        self.img_height = self.input_shape[2]
        self.img_width = self.input_shape[3]
        
        # 6. Detection parameters
        self.confidence_threshold = 0.5
        self.iou_threshold = 0.4
        
        # 7. Open webcam
        self.cap = cv2.VideoCapture(0)  # 0 = كاميرا اللاب
        
        if not self.cap.isOpened():
            self.get_logger().error("❌ Cannot open webcam!")
            raise RuntimeError("Failed to open webcam")
        
        # Set camera properties for better performance
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        self.get_logger().info("📷 Webcam opened successfully!")
        
        # 8. Create timer for processing frames (15 FPS)
        self.timer = self.create_timer(1.0/15.0, self.process_frame)
        
        self.get_logger().info("🚀 Detection pipeline started! Press Ctrl+C to stop.")
        self.get_logger().info("=" * 60)
    
    def load_class_names(self):
        """Load class names from data.yaml"""
        try:
            with open(self.yaml_path, 'r') as f:
                data = yaml.safe_load(f)
                names = data.get('names', [])
                
                # Handle both list and dict formats
                if isinstance(names, dict):
                    return list(names.values())
                return names
        except Exception as e:
            self.get_logger().warn(f"⚠️ Could not load data.yaml: {e}")
            return ['like']  # Default class name
    
    def preprocess_image(self, image):
        """Preprocess image for YOLO model"""
        # Resize image to model input size
        img_resized = cv2.resize(image, (self.img_width, self.img_height))
        
        # Convert BGR to RGB
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        
        # Normalize to [0, 1]
        img_normalized = img_rgb.astype(np.float32) / 255.0
        
        # Transpose to (C, H, W)
        img_transposed = np.transpose(img_normalized, (2, 0, 1))
        
        # Add batch dimension: (1, C, H, W)
        img_batch = np.expand_dims(img_transposed, axis=0)
        
        return img_batch
    
    def postprocess_detections(self, outputs, original_shape):
        """Process YOLO model outputs to extract detections"""
        # YOLOv8 output format: (1, 84, 8400) or (1, num_classes+4, num_predictions)
        # First 4 values: [x_center, y_center, width, height]
        # Remaining values: class scores
        
        output = outputs[0]  # Get first output
        
        # Transpose to (num_predictions, 84)
        if len(output.shape) == 3:
            output = output[0].T
        else:
            output = output.T
        
        detections = []
        orig_height, orig_width = original_shape[:2]
        
        for pred in output:
            # Extract box coordinates and class scores
            x_center, y_center, width, height = pred[:4]
            class_scores = pred[4:]
            
            # Get class with highest score
            class_id = int(np.argmax(class_scores))
            confidence = float(class_scores[class_id])
            
            # Filter by confidence threshold
            if confidence < self.confidence_threshold:
                continue
            
            # Convert from normalized coordinates to pixel coordinates
            x1 = int((x_center - width / 2) * orig_width / self.img_width)
            y1 = int((y_center - height / 2) * orig_height / self.img_height)
            x2 = int((x_center + width / 2) * orig_width / self.img_width)
            y2 = int((y_center + height / 2) * orig_height / self.img_height)
            
            # Get class name
            class_name = self.class_names[class_id] if class_id < len(self.class_names) else f"class_{class_id}"
            
            detections.append({
                'bbox': [x1, y1, x2, y2],
                'confidence': confidence,
                'class_id': class_id,
                'class_name': class_name
            })
        
        return detections
    
    def draw_detections(self, image, detections):
        """Draw bounding boxes and labels on image"""
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            confidence = det['confidence']
            class_name = det['class_name']
            
            # Draw rectangle
            color = (0, 255, 0) if class_name == 'like' else (255, 0, 0)
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            label = f"{class_name}: {confidence:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            
            # Background for text
            cv2.rectangle(image, (x1, y1 - label_size[1] - 10), 
                         (x1 + label_size[0], y1), color, -1)
            
            # Text
            cv2.putText(image, label, (x1, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        return image
    
    def process_frame(self):
        """Process one frame from webcam"""
        # Read frame
        ret, frame = self.cap.read()
        
        if not ret:
            self.get_logger().warn("⚠️ Failed to read frame from webcam")
            return
        
        # Store original frame for display
        display_frame = frame.copy()
        
        try:
            # 1. Preprocess
            input_tensor = self.preprocess_image(frame)
            
            # 2. Run inference
            outputs = self.session.run(self.output_names, {self.input_name: input_tensor})
            
            # 3. Postprocess
            detections = self.postprocess_detections(outputs, frame.shape)
            
            # 4. Check if 'like' is detected
            like_detected = any(det['class_name'] == 'like' for det in detections)
            
            # 5. Publish to ROS
            msg = Bool()
            msg.data = like_detected
            self.publisher_.publish(msg)
            
            # 6. Log detection
            if like_detected:
                like_dets = [d for d in detections if d['class_name'] == 'like']
                self.get_logger().info(f"👍 LIKE DETECTED! Count: {len(like_dets)}")
            
            # 7. Draw detections on frame
            display_frame = self.draw_detections(display_frame, detections)
            
            # 8. Add info text
            info_text = f"Detections: {len(detections)} | Like: {'YES' if like_detected else 'NO'}"
            cv2.putText(display_frame, info_text, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # 9. Show frame
            cv2.imshow("YOLOv8 Like Detection", display_frame)
            cv2.waitKey(1)
            
        except Exception as e:
            self.get_logger().error(f"❌ Error during inference: {e}")
    
    def destroy_node(self):
        """Cleanup resources"""
        if hasattr(self, 'cap'):
            self.cap.release()
        cv2.destroyAllWindows()
        self.get_logger().info("👋 Node stopped. Goodbye!")
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    
    try:
        node = LikeDetectorNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
