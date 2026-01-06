#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import pandas as pd
import os
import json
from datetime import datetime

class OrderLogger(Node):
    def __init__(self):
        super().__init__('order_logger')
        
        # Subscribe to delivery report topic (Final Status)
        self.sub_report = self.create_subscription(
            String,
            '/delivery_report',
            self.on_report,
            10
        )
        
        # Subscribe to Order Creation (Real-time Initial Log)
        self.sub_order = self.create_subscription(
            String,
            '/order/json',
            self.on_order_created,
            10
        )
        
        # CSV File Path (Inside Package/Dashboard)
        # Using absolute path to source for persistence across rebuilds in this dev usage
        self.csv_path = os.path.expanduser('~/ws/src/App/order_logger/dashboard/delivery_log.csv')
        
        # Define Columns (Strict Order)
        self.columns = [
            "Date_Full",
            "Year",
            "Month",
            "Day_Name",
            "Time_Arrival",
            "Order_ID",
            "Target_Location",
            "QR_Scan_Status",
            "Client_Gesture_Status",
            "Handover_Time_Sec",
            "Trip_Duration_Min",
            "Distance_Traveled_M",
            "Order_Final_Status"
        ]
        
        self.get_logger().info(f'Order Logger Ready. Saving/Updating: {self.csv_path}')

    def on_order_created(self, msg: String):
        """Handle new order: Create 'Pending' entry immediately."""
        try:
            data = json.loads(msg.data)
            order_id = data.get("order_id")
            
            if not order_id:
                return

            self.get_logger().info(f"🆕 New Order detected: {order_id}. Logging initial state...")
            
            now = datetime.now()
            
            # Initial Row Data
            row_data = {
                "Date_Full": now.strftime("%Y-%m-%d"),
                "Year": now.strftime("%Y"),
                "Month": now.strftime("%B"),
                "Day_Name": now.strftime("%A"),
                "Time_Arrival": now.strftime("%H:%M:%S"),
                "Order_ID": order_id,
                "Target_Location": data.get("target_location", "N/A"),
                "QR_Scan_Status": "Pending",
                "Client_Gesture_Status": "Pending",
                "Handover_Time_Sec": 0,
                "Trip_Duration_Min": 0.0,
                "Distance_Traveled_M": 0.0,
                "Order_Final_Status": "In Progress"
            }
            
            self.update_csv(row_data, is_new=True)
            
        except Exception as e:
            self.get_logger().error(f"Failed to log new order: {e}")

    def on_report(self, msg: String):
        """Handle mission completion: Update existing entry."""
        try:
            # 1. Parse JSON Payload
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError:
                return

            order_id = data.get("order_id")
            if not order_id:
                return
                
            self.get_logger().info(f"✅ Mission Report for {order_id}. Updating log...")

            # 2. Construct Update Data (Only fields that change)
            # We assume Time_Arrival etc might be refined, or keep original? 
            # Let's overwrite with report data as it's the 'final truth'.
            
            now = datetime.now()
            row_data = {
                # "Date_Full": now.strftime("%Y-%m-%d"), # Keep original date?
                # "Time_Arrival": now.strftime("%H:%M:%S"), # Keep original time?
                "Order_ID": order_id, # Key
                "QR_Scan_Status": data.get("qr_scan_status", "N/A"),
                "Client_Gesture_Status": data.get("client_gesture_status", "N/A"),
                "Handover_Time_Sec": data.get("handover_time_sec", 0),
                "Trip_Duration_Min": data.get("trip_duration_min", 0.0),
                "Distance_Traveled_M": data.get("distance_traveled_m", 0.0),
                "Order_Final_Status": data.get("order_final_status", "Unknown")
            }
            
            self.update_csv(row_data, is_new=False)
            
        except Exception as e:
            self.get_logger().error(f"Failed to process report: {e}")

    def update_csv(self, row_data, is_new=True):
        try:
            df = pd.DataFrame()
            if os.path.exists(self.csv_path):
                try:
                    df = pd.read_csv(self.csv_path)
                except Exception:
                    df = pd.DataFrame(columns=self.columns)
            else:
                df = pd.DataFrame(columns=self.columns)
            
            target_id = row_data.get("Order_ID")
            
            if is_new:
                # Check if already exists to avoid duplicates
                if not df.empty and target_id in df['Order_ID'].astype(str).values:
                    self.get_logger().warn(f"Order {target_id} already exists. Skipping creation.")
                    return
                
                # Append
                new_df = pd.DataFrame([row_data])
                # Ensure cols
                for col in self.columns:
                    if col not in new_df.columns:
                        new_df[col] = "N/A"
                
                df = pd.concat([df, new_df[self.columns]], ignore_index=True)
                
            else:
                # Update
                if df.empty or target_id not in df['Order_ID'].astype(str).values:
                    self.get_logger().warn(f"Order {target_id} not found for update. Appending as new.")
                    # Fallback: Append
                    # We need to fill missing fields (Date etc) if we are appending from report only
                    # For now just let it have N/As
                    new_df = pd.DataFrame([row_data])
                    for col in self.columns:
                        if col not in new_df.columns:
                            new_df[col] = "N/A"
                    df = pd.concat([df, new_df[self.columns]], ignore_index=True)
                else:
                    # Finds index
                    idx = df.index[df['Order_ID'].astype(str) == str(target_id)].tolist()[0]
                    # Update fields present in row_data
                    for key, val in row_data.items():
                        if key in df.columns:
                            df.at[idx, key] = val
            
            df.to_csv(self.csv_path, index=False)
            self.get_logger().info(f"💾 CSV Saved. Total records: {len(df)}")
            
        except Exception as e:
            self.get_logger().error(f"Failed to write CSV: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = OrderLogger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
