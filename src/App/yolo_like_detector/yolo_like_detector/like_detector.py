#!/usr/bin/env python3

# Standard ROS 2 imports
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String # Import String for receiving commands
from ament_index_python.packages import get_package_share_directory

# Standard Python and utility imports
import os
import cv2
import numpy as np
import onnxruntime as ort
import yaml
from gtts import gTTS
import pygame
import time # تم استيراده لاستخدامه في time.sleep()

# --- Configuration Constants ---
# ROS Topic used by the Android app to send the 'start detection' command
ANDROID_COMMAND_TOPIC = '/delivery_commands'
# The specific command payload expected from the Android app
START_DETECTION_PAYLOAD = 'START_LIKE_DETECTION'
# ROS Topic to send the final robot command (CORRECTED to target app_goal_gateway)
ROBOT_GO_TOPIC = '/app/goal_name' 
# The command payload is the name of the base station pose 
ROBOT_GO_PAYLOAD = 'BASE' 
# -----------------------------


class LikeDetectorNode(Node):
    def __init__(self):
        super().__init__('like_detector_node')
        
        # --- 1. PUBLISHERS ---
        # Original publisher for the detection status (like_detected)
        self.status_publisher = self.create_publisher(Bool, '/like_detected', 10)
        self.get_logger().info("ROS 2 Status Publisher for /like_detected is ready.")
        
        # CORRECTED: Publisher to send the final 'Go' command to the robot 
        self.control_publisher = self.create_publisher(String, ROBOT_GO_TOPIC, 10)
        self.get_logger().info(f"ROS 2 Control Publisher for {ROBOT_GO_TOPIC} is ready.")

        # --- 2. SUBSCRIBER ---
        # Subscriber to listen for the command from the Android app
        self.command_subscriber = self.create_subscription(
            String,
            ANDROID_COMMAND_TOPIC,
            self.command_callback, # The function that runs when the command is received
            10
        )
        self.get_logger().info(f"Listening for Android command on {ANDROID_COMMAND_TOPIC}...")

        # --- 3. MODEL AND CAMERA INITIALIZATION ---
        pkg_share_dir = get_package_share_directory('yolo_like_detector')
        self.model_path = os.path.join(pkg_share_dir, 'weights', 'best.onnx')
        self.yaml_path = os.path.join(pkg_share_dir, 'weights', 'data.yaml')

        if not os.path.exists(self.model_path):
            self.get_logger().error(f"ONNX model not found: {self.model_path}")
            raise FileNotFoundError(f"Model not found: {self.model_path}")

        self.class_names = self.load_class_names()
        self.session = ort.InferenceSession(self.model_path)
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        self.output_names = [out.name for out in self.session.get_outputs()]

        self.img_height = self.input_shape[2]
        self.img_width = self.input_shape[3]
        self.confidence_threshold = 0.5
        self.iou_threshold = 0.4

        # Webcam is NOT opened yet (opened only when detection starts)
        self.cap = None 
        pygame.mixer.init()

        # --- 4. STATE MANAGEMENT ---
        self.detection_active = False 
        self.detection_made = False   
        self.timeout_duration = 60.0
        self.start_time = 0.0
        self.frame_timer = None 

    # ------------------------------------------------------------------
    # --- UTILITY METHODS (Keep as they are) ---
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

            # Wait only for the audio to start playing, not finish
            # while pygame.mixer.music.get_busy():
            #     pygame.time.Clock().tick(10)

            # os.remove(audio_file) # Will be removed after node shutdown
            self.get_logger().info("Audio message started successfully")

        except Exception as e:
            self.get_logger().error(f"Error playing audio: {e}")
    
    def speak_message(self, message):
        """Plays an audio message to guide the user."""
        try:
            tts = gTTS(text=message, lang='en', slow=False)
            audio_file = "/tmp/guidance_message.mp3"
            tts.save(audio_file)
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
        except Exception as e:
            self.get_logger().error(f"Error playing guidance audio: {e}")
            
    # ------------------------------------------------------------------
    # --- ROS CONTROL METHODS (NEW) ---
    def command_callback(self, msg):
        """
        ROS 2 Subscriber callback executed when a command is received from the Android app.
        Checks if the command is the trigger to start detection.
        """
        self.get_logger().info(f"Received command: {msg.data}")

        if msg.data == START_DETECTION_PAYLOAD and not self.detection_active:
            self.get_logger().info("START_LIKE_DETECTION command received. Initiating camera and timer.")
            self.start_detection_process()
        elif self.detection_active:
            self.get_logger().warn("Command received, but detection is already active.")

    def start_detection_process(self):
        """
        Initializes the camera, resets state, and starts the processing timer.
        """
        try:
            # 1. Open Webcam
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                self.get_logger().error("Cannot open webcam")
                raise RuntimeError("Failed to open webcam")

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.get_logger().info("Webcam opened successfully")
            
            # 2. Reset States
            self.detection_active = True
            self.detection_made = False
            self.start_time = time.time()
            
            # 3. Start the Timer 
            self.frame_timer = self.create_timer(1.0/15.0, self.process_frame)
            self.get_logger().info("Detection pipeline timer started.")
            
            # Show a message to the customer
            self.speak_message("Please show the 'Like' gesture to the robot's camera to confirm delivery.")

        except Exception as e:
            self.get_logger().error(f"Failed to start detection process: {e}")
            self.stop_detection_process()

    def stop_detection_process(self, success=False):
        """
        Stops the timer, releases resources, and sends the final ROS command if successful.
        """
        # 1. Destroy Timer
        if self.frame_timer is not None:
            self.frame_timer.destroy()
            self.frame_timer = None
        
        # 2. Release Webcam
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
        
        # 3. Close CV2 Windows
        cv2.destroyAllWindows()
        
        # 4. Update State
        self.detection_active = False
        
        if success:
            # Send the final 'Go' command to the robot control topic
            go_msg = String()
            go_msg.data = ROBOT_GO_PAYLOAD
            self.control_publisher.publish(go_msg)
            self.get_logger().info(f"FINAL COMMAND SENT: {ROBOT_GO_PAYLOAD} to {ROBOT_GO_TOPIC}")

        self.get_logger().info("Detection pipeline stopped.")
    
    # ------------------------------------------------------------------
    # --- CORE DETECTION LOOP (MODIFIED) ---
    def process_frame(self):
        """
        Called by the timer. Runs the detection logic frame by frame.
        """
        if not self.detection_active:
            return

        elapsed_time = time.time() - self.start_time

        # --- 1. Timeout Check ---
        if elapsed_time > self.timeout_duration:
            self.get_logger().warn("Detection timeout reached. Stopping detection.")
            self.stop_detection_process(success=False) 
            return

        ret, frame = self.cap.read()
        if not ret:
            self.get_logger().warn("Failed to read frame from webcam")
            return

        display_frame = frame.copy()

        # --- 2. Detection Logic ---
        try:
            input_tensor = self.preprocess_image(frame)
            outputs = self.session.run(self.output_names, {self.input_name: input_tensor})
            detections = self.postprocess_detections(outputs, frame.shape)

            like_detected = any(det['class_name'] == 'like' for det in detections)

            # Publish the detection status
            msg = Bool()
            msg.data = like_detected
            self.status_publisher.publish(msg)

            # --- 3. Success Check and Stop ---
            if like_detected and not self.detection_made:
                like_dets = [d for d in detections if d['class_name'] == 'like']
                self.get_logger().info(f"SUCCESS: Like detected. Count: {len(like_dets)}. Stopping process.")
                self.detection_made = True
                self.play_thank_you_message()
                
                # ADDED DELAY: Ensures the control command is published successfully before crashing/closing
                time.sleep(1.0) 
                
                self.stop_detection_process(success=True) # Send 'Go' command
                return # Exit the frame processing immediately

            # --- 4. Display Frame ---
            display_frame = self.draw_detections(display_frame, detections)
            
            remaining_time = int(self.timeout_duration - elapsed_time)
            info_text = f"Waiting for LIKE | Time Left: {remaining_time}s"
            cv2.putText(display_frame, info_text, (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            cv2.imshow("YOLOv8 Like Detection", display_frame)
            cv2.waitKey(1)

        except Exception as e:
            self.get_logger().error(f"Error during inference: {e}")


    def destroy_node(self):
        # Ensure all resources are released when the Node is shut down
        self.stop_detection_process(success=False)
        pygame.mixer.quit()
        self.get_logger().info("Node stopped")
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    
    node = None
    try:
        node = LikeDetectorNode()
        # The node starts immediately and waits for the command via the subscriber
        rclpy.spin(node) 
    except KeyboardInterrupt:
        print("\nStopped by user (Ctrl+C)")
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
