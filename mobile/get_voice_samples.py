import asyncio
import edge_tts
import os

# Create samples directory
if not os.path.exists("voice_samples"):
    os.makedirs("voice_samples")

TEXT_EN = "Hello! I am your new voice assistant. How can I help you today?"
TEXT_AR = "مرحباً! أنا مساعدك الصوتي الجديد. كيف يمكنني مساعدتك اليوم؟"

# Curated list of high-quality English Male voices
VOICES = [
    # US Accents (General & Diverse)
    {"name": "en-US-ChristopherNeural", "alias": "Christopher (Male - US)", "lang": "en"},
    {"name": "en-US-GuyNeural", "alias": "Guy (Male - US)", "lang": "en"},
    {"name": "en-US-EricNeural", "alias": "Eric (Male - US)", "lang": "en"},
    {"name": "en-US-RogerNeural", "alias": "Roger (Male - US)", "lang": "en"},
    {"name": "en-US-SteffanNeural", "alias": "Steffan (Male - US)", "lang": "en"},
    
    # UK Accents (British)
    {"name": "en-GB-RyanNeural", "alias": "Ryan (Male - UK)", "lang": "en"},
    {"name": "en-GB-ThomasNeural", "alias": "Thomas (Male - UK)", "lang": "en"},
    {"name": "en-GB-AlfieNeural", "alias": "Alfie (Male - UK)", "lang": "en"},
    
    # Other English Accents
    {"name": "en-AU-WilliamNeural", "alias": "William (Male - Australia)", "lang": "en"},
    {"name": "en-CA-LiamNeural", "alias": "Liam (Male - Canada)", "lang": "en"},
    {"name": "en-IN-PrabhatNeural", "alias": "Prabhat (Male - India)", "lang": "en"},
]

async def generate_samples():
    print("Generating voice samples...")
    for v in VOICES:
        text = TEXT_AR if v["lang"] == "ar" else TEXT_EN
        filename = f"voice_samples/{v['alias'].replace(' ', '_').replace('(', '').replace(')', '')}.mp3"
        
        print(f"Generating: {v['alias']} ({v['name']})...")
        try:
            communicate = edge_tts.Communicate(text, v["name"])
            await communicate.save(filename)
            print(f"  -> Saved to {filename}")
        except Exception as e:
            print(f"  -> Failed: {e}")

if __name__ == "__main__":
    asyncio.run(generate_samples())
