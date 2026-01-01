#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String
from sensor_msgs.msg import CompressedImage
from ament_index_python.packages import get_package_share_directory
import os
import cv2
import numpy as np
import onnxruntime as ort
import yaml
from gtts import gTTS
import pygame
import time
import json


class LikeDetectorNode(Node):
    def __init__(self):
        super().__init__('pipeline_ros_bridge')
        
        self.publisher_ = self.create_publisher(Bool, '/like_detected', 10)
        self.get_logger().info("ROS 2 Publisher for /like_detected is ready.")

        # Subscriptions
        self.image_sub = self.create_subscription(
            CompressedImage, '/camera/image_raw/compressed', self.image_callback, 10
        )
        self.status_sub = self.create_subscription(
            String, '/app/goal_status', self.on_status, 10
        )
        self.goal_name_sub = self.create_subscription(
            String, '/app/goal_name', self.on_goal_name, 10
        )
        # NEW: Listen for QR verification result
        self.verified_sub = self.create_subscription(
            Bool, '/robot/qr/verified', self.on_verified, 10
        )
        
        pkg_share_dir = get_package_share_directory('yolo_like_detector')
        self.model_path = os.path.join(pkg_share_dir, 'weights', 'best.onnx')
        self.yaml_path = os.path.join(pkg_share_dir, 'config', 'data.yaml')
        
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
        
        self.img_height = self.input_shape[2]
        self.img_width = self.input_shape[3]
        
        self.confidence_threshold = 0.5
        
        pygame.mixer.init()
        
        # State management
        self.detection_enabled = False
        self.detection_made = False
        self.current_destination = None
        
        self.get_logger().info("Like Detector Node (Passive) ready. Waiting for QR Verification...")
    
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

    # -------------------------------------------------------------------------
    # Helper: Manual Image Conversion (NumPy 2.x compatible)
    # -------------------------------------------------------------------------
    def imgmsg_to_cv2(self, img_msg):
        """
        Manually convert a sensor_msgs/CompressedImage to an OpenCV image.
        """
        try:
            np_arr = np.frombuffer(img_msg.data, np.uint8)
            im = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            return im
        except Exception as e:
            self.get_logger().error(f"Failed to convert compressed image: {e}")
            return None

    # -------------------------------------------------------------------------
    # Topic Callbacks
    # -------------------------------------------------------------------------

    def on_goal_name(self, msg: String):
        try:
            self.current_destination = msg.data.strip()
        except Exception:
            pass

    def on_status(self, msg: String):
        """
        Handle robot arrival/departure status.
        - Arrived: Do NOTHING (wait for QR verification).
        - Departed: Disable detection.
        """
        try:
            st = json.loads(msg.data)
            arrived = bool(st.get('arrived', False))
        except Exception:
            payload = (msg.data or "").lower()
            arrived = 'arrived' in payload or 'succeeded' in payload

        if not arrived:
            # If robot moves away, disable detection immediately
            if self.detection_enabled:
                self.get_logger().info("Robot left destination - Disabling Like Detection.")
                self.detection_enabled = False
                cv2.destroyAllWindows()

    def on_verified(self, msg: Bool):
        """
        Trigger detection when QR code is successfully verified.
        """
        if msg.data: # True => Verified
            if not self.detection_enabled:
                self.get_logger().info("✅ QR Verified! Enabling Like Detection sequence.")
                self.detection_enabled = True
                self.detection_made = False  # Reset for new interaction
        else:
            self.get_logger().info("QR Verification failed (or false signal received).")


    def image_callback(self, msg):
        if not self.detection_enabled:
            return

        frame = self.imgmsg_to_cv2(msg)
        if frame is None:
            return

        try:
            input_tensor = self.preprocess_image(frame)
            outputs = self.session.run(self.output_names, {self.input_name: input_tensor})
            detections = self.postprocess_detections(outputs, frame.shape)
            
            like_detected = any(det['class_name'] == 'like' for det in detections)
            
            msg_out = Bool()
            msg_out.data = like_detected
            self.publisher_.publish(msg_out)
            
            if like_detected and not self.detection_made:
                like_dets = [d for d in detections if d['class_name'] == 'like']
                self.get_logger().info(f"Like detected! Count: {len(like_dets)}")
                self.detection_made = True
                self.play_thank_you_message()
            
            # Visualization
            display_frame = frame.copy()
            display_frame = self.draw_detections(display_frame, detections)
            
            info_text = f"Like: {'YES' if like_detected else 'NO'}"
            cv2.putText(display_frame, info_text, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.imshow("YOLOv8 Like Detection", display_frame)
            cv2.waitKey(1)
            
        except Exception as e:
            self.get_logger().error(f"Error during inference: {e}")
    
    # -------------------------------------------------------------------------
    # Inference Helpers
    # -------------------------------------------------------------------------
    
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
    
    def destroy_node(self):
        cv2.destroyAllWindows()
        pygame.mixer.quit()
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
