import asyncio
import edge_tts
import os
import pygame
import time

VOICE = "en-US-RogerNeural"
TEXT = "Hello! I am Roger. I am the voice you selected. I can help you verify deliveries."

async def play_voice():
    print(f"Generating audio regarding to: {VOICE}...")
    filename = "/tmp/test_roger.mp3"
    
    communicate = edge_tts.Communicate(TEXT, VOICE)
    await communicate.save(filename)
    
    print("Playing audio...")
    pygame.mixer.init()
    pygame.mixer.music.load(filename)
    pygame.mixer.music.play()
    
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
        
    os.remove(filename)
    print("Done.")

if __name__ == "__main__":
    asyncio.run(play_voice())
