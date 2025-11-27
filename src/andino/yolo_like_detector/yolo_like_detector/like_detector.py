#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
from ament_index_python.packages import get_package_share_directory
import os
import cv2
import numpy as np
import onnxruntime as ort
import yaml
from gtts import gTTS
import pygame
import time

class LikeDetectorNode(Node):
    def __init__(self):
        super().__init__('pipeline_ros_bridge')
        
        self.publisher_ = self.create_publisher(Bool, '/like_detected', 10)
        self.get_logger().info("ROS 2 Publisher for /like_detected is ready.")
        
        pkg_share_dir = get_package_share_directory('yolo_like_detector')
        self.model_path = os.path.join(pkg_share_dir, 'weights', 'best.onnx')
        self.yaml_path = os.path.join(pkg_share_dir, 'weights', 'data.yaml')
        
        if not os.path.exists(self.model_path):
            self.get_logger().error(f"ONNX model not found: {self.model_path}")
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        
        self.get_logger().info(f"Loading ONNX model: {self.model_path}")
        
        self.class_names = self.load_class_names()
        self.get_logger().info(f"Classes loaded: {self.class_names}")
        
        self.session = ort.InferenceSession(self.model_path)
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        self.output_names = [out.name for out in self.session.get_outputs()]
        
        self.get_logger().info(f"Model input: {self.input_name}, shape: {self.input_shape}")
        self.get_logger().info(f"Model outputs: {self.output_names}")
        
        self.img_height = self.input_shape[2]
        self.img_width = self.input_shape[3]
        
        self.confidence_threshold = 0.5
        self.iou_threshold = 0.4
        
        self.cap = cv2.VideoCapture(0)
        
        if not self.cap.isOpened():
            self.get_logger().error("Cannot open webcam")
            raise RuntimeError("Failed to open webcam")
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        self.get_logger().info("Webcam opened successfully")
        
        pygame.mixer.init()
        
        self.detection_made = False
        self.start_time = time.time()
        self.timeout_duration = 60.0
        
        self.timer = self.create_timer(1.0/15.0, self.process_frame)
        
        self.get_logger().info("Detection pipeline started. Press Ctrl+C to stop.")
    
    def load_class_names(self):
        try:
            with open(self.yaml_path, 'r') as f:
                data = yaml.safe_load(f)
                names = data.get('names', [])
                
                if isinstance(names, dict):
                    return list(names.values())
                return names
        except Exception as e:
            self.get_logger().warn(f"Could not load data.yaml: {e}")
            return ['like']
    
    def preprocess_image(self, image):
        img_resized = cv2.resize(image, (self.img_width, self.img_height))
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        img_normalized = img_rgb.astype(np.float32) / 255.0
        img_transposed = np.transpose(img_normalized, (2, 0, 1))
        img_batch = np.expand_dims(img_transposed, axis=0)
        
        return img_batch
    
    def postprocess_detections(self, outputs, original_shape):
        output = outputs[0]
        
        if len(output.shape) == 3:
            output = output[0].T
        else:
            output = output.T
        
        detections = []
        orig_height, orig_width = original_shape[:2]
        
        for pred in output:
            x_center, y_center, width, height = pred[:4]
            class_scores = pred[4:]
            
            class_id = int(np.argmax(class_scores))
            confidence = float(class_scores[class_id])
            
            if confidence < self.confidence_threshold:
                continue
            
            x1 = int((x_center - width / 2) * orig_width / self.img_width)
            y1 = int((y_center - height / 2) * orig_height / self.img_height)
            x2 = int((x_center + width / 2) * orig_width / self.img_width)
            y2 = int((y_center + height / 2) * orig_height / self.img_height)
            
            class_name = self.class_names[class_id] if class_id < len(self.class_names) else f"class_{class_id}"
            
            detections.append({
                'bbox': [x1, y1, x2, y2],
                'confidence': confidence,
                'class_id': class_id,
                'class_name': class_name
            })
        
        return detections
    
    def draw_detections(self, image, detections):
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            confidence = det['confidence']
            class_name = det['class_name']
            
            color = (0, 255, 0) if class_name == 'like' else (255, 0, 0)
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            
            label = f"{class_name}: {confidence:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            
            cv2.rectangle(image, (x1, y1 - label_size[1] - 10), 
                         (x1 + label_size[0], y1), color, -1)
            
            cv2.putText(image, label, (x1, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        return image
    
    def play_thank_you_message(self):
        try:
            message = "We're so glad your order arrived! Thank you for being a valued customer."
            tts = gTTS(text=message, lang='en', slow=False)
            
            audio_file = "/tmp/thank_you_message.mp3"
            tts.save(audio_file)
            
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            
            os.remove(audio_file)
            self.get_logger().info("Audio message played successfully")
            
        except Exception as e:
            self.get_logger().error(f"Error playing audio: {e}")
    
    def process_frame(self):
        elapsed_time = time.time() - self.start_time
        
        if elapsed_time > self.timeout_duration or self.detection_made:
            self.get_logger().info("Detection timeout reached or detection completed. Shutting down.")
            self.cap.release()
            cv2.destroyAllWindows()
            rclpy.shutdown()
            return
        
        ret, frame = self.cap.read()
        
        if not ret:
            self.get_logger().warn("Failed to read frame from webcam")
            return
        
        display_frame = frame.copy()
        
        try:
            input_tensor = self.preprocess_image(frame)
            outputs = self.session.run(self.output_names, {self.input_name: input_tensor})
            detections = self.postprocess_detections(outputs, frame.shape)
            
            like_detected = any(det['class_name'] == 'like' for det in detections)
            
            msg = Bool()
            msg.data = like_detected
            self.publisher_.publish(msg)
            
            if like_detected and not self.detection_made:
                like_dets = [d for d in detections if d['class_name'] == 'like']
                self.get_logger().info(f"Like detected. Count: {len(like_dets)}")
                self.detection_made = True
                self.play_thank_you_message()
            
            display_frame = self.draw_detections(display_frame, detections)
            
            remaining_time = int(self.timeout_duration - elapsed_time)
            info_text = f"Detections: {len(detections)} | Like: {'YES' if like_detected else 'NO'} | Time: {remaining_time}s"
            cv2.putText(display_frame, info_text, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.imshow("YOLOv8 Like Detection", display_frame)
            cv2.waitKey(1)
            
        except Exception as e:
            self.get_logger().error(f"Error during inference: {e}")
    
    def destroy_node(self):
        if hasattr(self, 'cap'):
            self.cap.release()
        cv2.destroyAllWindows()
        pygame.mixer.quit()
        self.get_logger().info("Node stopped")
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    
    try:
        node = LikeDetectorNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
