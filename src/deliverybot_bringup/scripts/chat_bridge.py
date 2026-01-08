#!/usr/bin/env python3
"""
Chat Bridge Node - Connects Mobile App to Llama AI
Subscribes: /app/chat/request (std_msgs/String)
Publishes:  /app/chat/response (std_msgs/String)
Uses:       /llama/generate_response action
            /say action (TTS)
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from std_msgs.msg import String
from geometry_msgs.msg import Twist
import pandas as pd
import os
import time
import datetime
import datetime
import uuid
import re

# Try to import Audio Common for TTS
try:
    from audio_common_msgs.action import TTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# Try to import llama_msgs
try:
    from llama_msgs.action import GenerateResponse
    LLAMA_AVAILABLE = True
except ImportError:
    LLAMA_AVAILABLE = False


class ChatBridge(Node):
    def __init__(self):
        unique_id = str(uuid.uuid4())[:8]
        super().__init__(f'chat_bridge_{unique_id}')
        
        # Publisher for responses
        self.response_pub = self.create_publisher(String, '/app/chat/response', 10)
        
        # Subscriber for requests
        self.request_sub = self.create_subscription(
            String, '/app/chat/request', self.on_request, 10)
        
        # TTS Action Client
        if TTS_AVAILABLE:
            self.tts_client = ActionClient(self, TTS, '/say')
            self.get_logger().info('TTS Support Enabled')
        else:
            self.tts_client = None
            self.get_logger().warn('TTS msgs not found - Voice disabled')

        # Llama action client
        if LLAMA_AVAILABLE:
            self.llama_client = ActionClient(
                self, GenerateResponse, '/llama/generate_response')
            self.get_logger().info('Chat Bridge started with Llama AI support')
        else:
            self.llama_client = None
            self.get_logger().warn('Llama msgs not found - using echo mode')
        
        self.get_logger().info('Chat Bridge ready: /app/chat/request -> Llama -> /app/chat/response')
        
        # VISUAL SENSES
        self.latest_vision = "Nothing detected yet"
        self.vision_sub = self.create_subscription(String, '/yolo/detections_str', self.on_vision, 10)
        
        # COMMAND OUTPUT
        self.cmd_pub = self.create_publisher(String, '/app/goal_name', 10)
        self.vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # Streaming response accumulator
        self._accumulated_response = ""
        self._is_generating = False

    def on_vision(self, msg: String):
        self.latest_vision = msg.data

    def execute_command(self, response_text):
        # 1. NAVIGATION (Go to X)
        if "[COMMAND:" in response_text:
            try:
                start = response_text.find("[COMMAND:") + 9
                end = response_text.find("]", start)
                if end != -1:
                    cmd_val = response_text[start:end].strip()
                    self.get_logger().info(f"🤖 NAV CMD: Go to {cmd_val}")
                    msg = String()
                    msg.data = cmd_val
                    self.cmd_pub.publish(msg)
                    return True
            except Exception as e:
                self.get_logger().error(f"Nav parsing error: {e}")

        # 2. MOTION (Move Forward, Stop, etc)
        if "[ACTION:" in response_text:
            try:
                start = response_text.find("[ACTION:") + 8
                end = response_text.find("]", start)
                if end != -1:
                    action = response_text[start:end].strip().upper()
                    self.get_logger().info(f"🤖 MOTION CMD: {action}")
                    
                    twist = Twist()
                    if action == "FORWARD":
                        twist.linear.x = 0.2
                    elif action == "BACKWARD":
                        twist.linear.x = -0.2
                    elif action == "LEFT":
                        twist.angular.z = 0.5
                    elif action == "RIGHT":
                        twist.angular.z = -0.5
                    elif action == "STOP":
                        twist.linear.x = 0.0
                        twist.angular.z = 0.0
                    
                    # Publish a burst to ensure movement
                    for _ in range(5):
                        self.vel_pub.publish(twist)
                        time.sleep(0.1)
                        
                    return True
            except Exception as e:
                self.get_logger().error(f"Motion parsing error: {e}")
        
        return False

    def get_robot_stats(self):
        """Reads CSV and returns the last 5 deliveries."""
        csv_path = os.path.expanduser('~/ws/src/App/order_logger/dashboard/delivery_log.csv')
        if not os.path.exists(csv_path):
            return "No history available."
            
        try:
            df = pd.read_csv(csv_path)
            if df.empty:
                return "History is empty."
            
            # Get last 5 rows
            last_5 = df.tail(5)
            history_str = "HISTORY (Last 5 trips):\n"
            for _, row in last_5.iterrows():
                history_str += f"- {row['Date_Full']} {row['Time_Arrival']}: To {row.get('Target_Location', 'Unknown')} ({row.get('Order_Final_Status', 'Unknown')})\n"
                
            return history_str
        except Exception as e:
            self.get_logger().error(f"Stats error: {e}")
            return "Error reading history."

    def on_request(self, msg: String):
        user_text = msg.data.strip()
        if not user_text:
            return
        
        self.get_logger().info(f'Received chat request: {user_text}')
        
        # Skip busy check - let Llama handle queuing
        if self._is_generating:
            self.get_logger().warn('Previous request still processing, will queue this one')
        
        if LLAMA_AVAILABLE and self.llama_client:
            self.send_to_llama(user_text)
        else:
            self.publish_response(f'Echo: {user_text}')

    def send_to_llama(self, prompt: str):
        if not self.llama_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().warn('Llama action server not available')
            self.publish_response('Sorry, AI is not available right now.')
            return
        
        # Reset accumulator
        self._accumulated_response = ""
        self._is_generating = True
        
        goal = GenerateResponse.Goal()
        
        # CONTEXT
        stats_context = self.get_robot_stats()
        vision_context = f"LIVE VISION: I currently see: {self.latest_vision}"
        
        now = datetime.datetime.now()
        time_context = f"CURRENT DATETIME: {now.strftime('%A, %Y-%m-%d %H:%M:%S')}"
        
        system_instr = (
            "You are a smart robot assistant managing deliveries. "
            "1. NAVIGATION: Only if user asks to go to a specific place, output [COMMAND: LocationName]. "
            "   Example: 'Go to Kitchen' -> '[COMMAND: Kitchen] Going to Kitchen.' "
            "2. MOTION: [ACTION: FORWARD], [ACTION: BACKWARD], [ACTION: LEFT], [ACTION: RIGHT], [ACTION: STOP]. "
            "3. INFO: Use the HISTORY below to answer questions about past deliveries. "
            "4. VISION: I will provide LIVE VISION data. Use it to answer 'What do you see?'. "
            "5. OUTPUT FORMAT: Check the user's language. "
            "   - IF USER SPEAKS ENGLISH: Reply in English. DO NOT use '|||'. "
            "   - IF USER SPEAKS ARABIC: Reply in Arabic, then YOU MUST append '|||' followed by the English translation. "
            "     Example: 'مرحباً ||| Hello there.'"
        )
        
        # ChatML Format
        full_prompt = (
            f"<|im_start|>system\n{system_instr}\n\n"
            f"{time_context}\n\n"
            f"{stats_context}\n\n"
            f"{vision_context}\n<|im_end|>\n"
            f"<|im_start|>user\n{prompt}\n<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        
        self.get_logger().info(f"PROMPT: {full_prompt}")
        
        goal.prompt = full_prompt
        goal.reset = True
        
        future = self.llama_client.send_goal_async(goal, feedback_callback=self.on_llama_feedback)
        future.add_done_callback(self.on_llama_goal_response)

    def on_llama_feedback(self, feedback_msg):
        try:
            partial = feedback_msg.feedback.partial_response
            token_text = partial.text if hasattr(partial, 'text') else ""
            if token_text:
                self._accumulated_response += token_text
        except Exception as e:
            self.get_logger().error(f'Feedback error: {e}')

    def on_llama_goal_response(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn('Goal rejected (AI busy)')
            self._is_generating = False
            return
        
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.on_llama_result)

    def on_llama_result(self, future):
        self._is_generating = False
        response_text = ""
        
        try:
            result = future.result().result
            if hasattr(result, 'response') and hasattr(result.response, 'text') and result.response.text:
                response_text = result.response.text
            elif hasattr(result, 'text') and result.text:
                response_text = result.text
        except Exception as e:
            self.get_logger().error(f'Result extraction error: {e}')

        if not response_text:
            response_text = self._accumulated_response.strip()
        
        if not response_text:
            response_text = "ERROR: Empty response from AI."
        
        self.get_logger().info(f'Final Llama response: {response_text[:100]}...')
        
        self.execute_command(response_text)
        
        # Clean Tags
        clean_text = response_text.replace("[COMMAND:", "").replace("[ACTION:", "").replace("]", "")
        clean_text = clean_text.replace("<|im_end|>", "").replace("<|im_start|>", "").strip()
        
        # Split for Dual Language (Chat vs Voice)
        chat_text = clean_text
        voice_text = clean_text
        
        if "|||" in clean_text:
            parts = clean_text.split("|||")
            chat_text = parts[0].strip()
            voice_text = parts[1].strip()
            
        # FORCE PROPER ENGLISH VOICE: Remove non-ascii characters from voice_text
        # This removes Arabic leaks, keeping only English, numbers, and punctuation.
        voice_text = re.sub(r'[^\x00-\x7F]+', '', voice_text).strip()
        
        self.get_logger().info(f"Dual Lang: Chat='{chat_text[:30]}...', Voice='{voice_text[:30]}...'")
        self.publish_response(chat_text, voice_text)

    def publish_response(self, chat_text: str, voice_text: str = None):
        if voice_text is None:
            voice_text = chat_text
            
        # 1. Text Response (User Language)
        msg = String()
        msg.data = chat_text
        self.response_pub.publish(msg)
        self.get_logger().info(f'Published chat: {chat_text[:50]}...')
        
        # 2. Voice Response (English Only)
        if self.tts_client:
            self.speak(voice_text)

    def speak(self, text: str):
        if not self.tts_client.wait_for_server(timeout_sec=0.5):
            # Don't block too long for voice
            self.get_logger().warn("TTS server taking too long, skipping voice")
            return
            
        goal = TTS.Goal()
        goal.text = text
        self.tts_client.send_goal_async(goal)

def main(args=None):
    rclpy.init(args=args)
    node = ChatBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
