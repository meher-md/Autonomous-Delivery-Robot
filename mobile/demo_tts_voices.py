import os
import sys
import soundfile as sf
import sherpa_onnx
import pyttsx3

def play_audio(filename):
    print(f"Playing {filename}...")
    os.system(f"aplay {filename}")

def demo_sherpa():
    print("-" * 30)
    print("Demonstrating Sherpa ONNX (Offline High Quality)")
    print("-" * 30)
    
    # Paths from Android assets
    base_assets = "/home/mo/ws/mobile/DeliveryBotApp/app/src/main/assets/sherpa"
    
    # Shared Data
    espeak_data = f"{base_assets}/model-en-female/espeak-ng-data"
    
    models = [
        {
            "name": "Rafiq (Male)",
            "model": f"{base_assets}/model-en-male/en_US-ryan-low.onnx",
            "tokens": f"{base_assets}/model-en-male/tokens.txt",
            "text": "Hello! I am Rafiq, your delivery assistant."
        },
        {
            "name": "Rafiqa (Female)",
            "model": f"{base_assets}/model-en-female/en_US-amy-low.onnx",
            "tokens": f"{base_assets}/model-en-female/tokens.txt",
            "text": "Hello! I am Rafiqa, here to help you."
        }
    ]

    for m in models:
        print(f"Generating audio for: {m['name']}")
        try:
            tts_config = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                        model=m["model"],
                        tokens=m["tokens"],
                        data_dir=espeak_data,
                    ),
                    num_threads=1,
                    debug=False,
                )
            )
            tts = sherpa_onnx.OfflineTts(tts_config)
            audio = tts.generate(m["text"], sid=0, speed=1.0)
            
            filename = f"{m['name'].split()[0].lower()}_sample.wav"
            sf.write(filename, audio.samples, audio.sample_rate)
            play_audio(filename)
            
        except Exception as e:
            print(f"Error generating {m['name']}: {e}")

def demo_pyttsx3():
    print("\n" + "-" * 30)
    print("Demonstrating System Voices (pyttsx3)")
    print("-" * 30)
    
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        
        for voice in voices:
            print(f"Voice: {voice.name}")
            engine.setProperty('voice', voice.id)
            engine.say(f"Hello, I am using the system voice {voice.name}")
            engine.runAndWait()
            
    except Exception as e:
        print(f"Error with pyttsx3: {e}")

if __name__ == "__main__":
    demo_sherpa()
    demo_pyttsx3()
