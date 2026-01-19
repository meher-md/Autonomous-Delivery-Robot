import asyncio
import edge_tts
import os
import pygame
import time

VOICE = "en-US-RogerNeural"

PHRASES = [
    "Hi! I am Rafiq. I am here. Can you please scan the QR code I sent you?",
    "Success! Please open the box and take your order. When you are done, please show me a Like sign."
]

async def play_voice():
    print(f"Testing Delivery Announcements with Voice: {VOICE}\n")
    if not pygame.mixer.get_init():
        pygame.mixer.init()
        
    for i, text in enumerate(PHRASES):
        print(f"[{i+1}] Speaking: '{text}'")
        filename = f"/tmp/delivery_test_{i}.mp3"
        
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(filename)
        
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        
        time.sleep(1.0) # Pause between phrases
        os.remove(filename)

    print("\nTest Complete.")

if __name__ == "__main__":
    asyncio.run(play_voice())
