import os
import shutil
import re
import datetime
import time

def parse_order_history(filepath):
    """
    Parses order_history.txt and returns list of dicts:
    [{'timestamp': epoch, 'file': filename}, ...]
    Sorted by timestamp.
    """
    orders = []
    current_order = {}
    
    # Regex for Timestamp line: "Timestamp: 2025-11-18 19:18:14 (1763486294)"
    ts_pattern = re.compile(r"Timestamp: .* \((\d+)\)")
    file_pattern = re.compile(r"QR Code File: (.*)")
    
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                match_ts = ts_pattern.search(line)
                if match_ts:
                    current_order['timestamp'] = int(match_ts.group(1))
                    
                match_file = file_pattern.search(line)
                if match_file:
                    current_order['file'] = match_file.group(1)
                    
                if line.startswith('=' * 20):
                    # End of block (or start), if we have collected data, save it
                    if 'timestamp' in current_order and 'file' in current_order:
                        orders.append(current_order)
                        current_order = {}
                        
        # Catch last one if file doesn't end with separator
        if 'timestamp' in current_order and 'file' in current_order:
            orders.append(current_order)
            
    except Exception as e:
        print(f"Error reading history: {e}")
        
    return sorted(orders, key=lambda x: x['timestamp'])

def get_mission_timestamp(mission_dir_path):
    """
    Extracts timestamp from path: 
    .../2026/January/03/mission_142939
    """
    try:
        # Split path
        parts = mission_dir_path.split(os.sep)
        # We need finding "mission_XXXXXX" and its parents
        mission_name = parts[-1]
        day = parts[-2]
        month_name = parts[-3]
        year = parts[-4]
        
        # Parse Month Name to Number
        try:
            dt_month = datetime.datetime.strptime(month_name, "%B")
            month_num = dt_month.month
        except:
             print(f"Failed to parse month: {month_name}")
             return None

        # Time part "mission_142939" -> "142939"
        if not mission_name.startswith("mission_"):
            return None
        time_str = mission_name.split("_")[1]
        
        dt_str = f"{year}-{month_num:02d}-{day} {time_str}"
        # Format: YYYY-MM-DD HHMMSS
        dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H%M%S")
        return int(dt.timestamp())
    except Exception as e:
        # print(f"Skipping {mission_dir_path}: {e}")
        return None

def backfill():
    history_path = os.path.expanduser("~/ws/order_history.txt")
    source_qr_dir = os.path.expanduser("~/ws/generated_qr")
    mission_root = os.path.expanduser("~/ws/mission_proof")
    
    orders = parse_order_history(history_path)
    print(f"Loaded {len(orders)} orders from history.")
    
    count = 0
    
    # Walk mission directory
    for root, dirs, files in os.walk(mission_root):
        for d in dirs:
            if d.startswith("mission_"):
                mission_path = os.path.join(root, d)
                
                # Check if already has the file
                if os.path.exists(os.path.join(mission_path, "generated_qr_original.png")):
                    continue
                    
                mission_ts = get_mission_timestamp(mission_path)
                if not mission_ts:
                    continue
                    
                # Find matching order
                # Strategy: Order must be BEFORE mission.
                # Find the closest order roughly within 60 mins before mission.
                
                best_match = None
                min_diff = 3600 * 24 # 24 hours init
                
                for order in orders:
                    diff = mission_ts - order['timestamp']
                    if diff >= 0 and diff < 3600: # Within 1 hour before
                        if diff < min_diff:
                            min_diff = diff
                            best_match = order
                            
                if best_match:
                    src_file = os.path.join(source_qr_dir, best_match['file'])
                    if os.path.exists(src_file):
                        dst_file = os.path.join(mission_path, "generated_qr_original.png")
                        shutil.copy2(src_file, dst_file)
                        print(f"Backfilled: {d} <- {best_match['file']} (Diff: {min_diff}s)")
                        count += 1
                    else:
                        print(f"Missing source file: {src_file}")
                else:
                    print(f"No matching order found for mission {d} (TS: {mission_ts})")

    print(f"Backfill complete. Copied {count} images.")

if __name__ == "__main__":
    backfill()
