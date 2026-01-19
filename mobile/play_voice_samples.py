import os
import time
import pygame

def play_samples():
    pygame.mixer.init()
    
    sample_dir = "voice_samples"
    if not os.path.exists(sample_dir):
        print("No samples found. Run get_voice_samples.py first.")
        return

    files = sorted([f for f in os.listdir(sample_dir) if f.endswith(".mp3")])
    
    print(f"Found {len(files)} samples in '{sample_dir}'\n")
    
    for f in files:
        path = os.path.join(sample_dir, f)
        clean_name = f.replace("_", " ").replace(".mp3", "")
        print(f"Playing: {clean_name} ...")
        
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
                
            time.sleep(0.5) # Pause between samples
        except Exception as e:
            print(f"Error playing {f}: {e}")

if __name__ == "__main__":
    play_samples()
