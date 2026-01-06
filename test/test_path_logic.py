import os
import datetime

def test_creation():
    # 1. Create Folder
    now = datetime.datetime.now()
    # Create hierarchy: Year/Month/Day
    year_str = now.strftime("%Y")
    month_str = now.strftime("%m")
    day_str = now.strftime("%d")
    
    # Mission specific folder with time only (since date is in hierarchy)
    mission_time_str = now.strftime("%H%M%S")
    folder_name = f"mission_{mission_time_str}"
    
    base_dir = os.path.expanduser("~/ws/mission_evidence_TEST") # Modified base for test
    # Full path: ~/ws/mission_evidence/YYYY/MM/DD/mission_HHMMSS
    mission_dir = os.path.join(base_dir, year_str, month_str, day_str, folder_name)
    print(f"Attempting to create: {mission_dir}")
    os.makedirs(mission_dir, exist_ok=True)
    
    if os.path.exists(mission_dir):
        print("SUCCESS: Directory created.")
    else:
        print("FAILURE: Directory not found.")

if __name__ == "__main__":
    test_creation()
