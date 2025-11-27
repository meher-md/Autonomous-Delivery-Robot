#!/usr/bin/env python3
"""
Monitor QR Scanner Status
This script monitors the QR scanner node to check if the laptop camera is active and scanning.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
from datetime import datetime

class QrScannerMonitor(Node):
    def __init__(self):
        super().__init__('qr_scanner_monitor')
        self.status_sub = self.create_subscription(
            String, 
            '/robot/qr/scanner_status', 
            self.on_status, 
            10
        )
        self.scan_sub = self.create_subscription(
            String,
            '/robot/qr/scanned',
            self.on_scan,
            10
        )
        self.get_logger().info('🔍 QR Scanner Monitor started')
        self.get_logger().info('📡 Listening to /robot/qr/scanner_status and /robot/qr/scanned')
        self.get_logger().info('Press Ctrl+C to stop\n')

    def on_status(self, msg: String):
        try:
            data = json.loads(msg.data)
            status = data.get('status', 'unknown')
            message = data.get('message', '')
            scanning = data.get('scanning', False)
            camera_opened = data.get('camera_opened', False)
            frames_processed = data.get('frames_processed', 0)
            timestamp = data.get('timestamp', 0)
            
            time_str = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S') if timestamp else 'N/A'
            
            # Color-coded status display
            status_icon = {
                'initialized': '⚙️',
                'starting': '🚀',
                'scanning': '📹',
                'qr_scanned': '✅',
                'stopped': '⏹️',
                'error': '❌'
            }.get(status, '❓')
            
            print(f'\n[{time_str}] {status_icon} Status: {status.upper()}')
            print(f'   Message: {message}')
            print(f'   Scanning: {"YES" if scanning else "NO"}')
            print(f'   Camera Open: {"YES ✅" if camera_opened else "NO ❌"}')
            print(f'   Frames Processed: {frames_processed}')
            
            if status == 'error':
                print(f'   ⚠️  ERROR DETECTED - Check logs for details')
            elif status == 'scanning' and camera_opened:
                print(f'   ✅ Camera is active and scanning for QR codes!')
                
        except Exception as e:
            self.get_logger().error(f'Error parsing status: {e}')

    def on_scan(self, msg: String):
        try:
            data = json.loads(msg.data)
            raw_data = data.get('raw', '')
            timestamp = data.get('timestamp', 0)
            time_str = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S') if timestamp else 'N/A'
            
            print(f'\n🎉 [{time_str}] QR CODE SCANNED!')
            print(f'   Data: {raw_data[:100]}...')
            print(f'   Full data published to /robot/qr/scanned')
            
        except Exception as e:
            self.get_logger().error(f'Error parsing scan: {e}')

def main():
    rclpy.init()
    monitor = QrScannerMonitor()
    try:
        print('=' * 60)
        print('QR Scanner Monitor - Waiting for status updates...')
        print('=' * 60)
        rclpy.spin(monitor)
    except KeyboardInterrupt:
        print('\n\n👋 Monitor stopped by user')
    finally:
        monitor.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

