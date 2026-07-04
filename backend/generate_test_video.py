"""Quick Veo 3 test video generation"""
import os
import time
from dotenv import load_dotenv
load_dotenv()

os.environ["REPLICATE_API_TOKEN"] = os.getenv("REPLICATE_API_TOKEN", "")

import replicate

print("🎬 Generating a test video via Veo 3...")
print("This takes 1-3 minutes\n")

prompt = "A beautiful woman with long dark hair walks through neon-lit Tokyo streets at night. Cinematic, 4K, rain reflections."

print(f"📝 Prompt: {prompt}")
print("⏳ Sending request...\n")

start = time.time()

prediction = replicate.predictions.create(
    model=replicate.models.get("google/veo-3-fast"),
    input={
        "prompt": prompt,
        "resolution": "720p",
        "duration": 4,
        "aspect_ratio": "9:16",
        "generate_audio": False
    }
)

print(f"🆔 Prediction ID: {prediction.id}")

while prediction.status not in ["succeeded", "failed", "canceled"]:
    time.sleep(5)
    prediction.reload()
    elapsed = int(time.time() - start)
    print(f"  [{elapsed:3d}s] {prediction.status}...")

elapsed = int(time.time() - start)

if prediction.status == "succeeded":
    print(f"\n✅ SUCCESS! Video ready in {elapsed} seconds")
    print(f"📹 URL: {prediction.output}")
else:
    print(f"\n❌ Error: {prediction.status}")
    if prediction.error:
        print(f"Details: {prediction.error}")
