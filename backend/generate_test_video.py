"""Quick Veo 3 test video generation"""
import os
import time
from dotenv import load_dotenv
load_dotenv()

os.environ["REPLICATE_API_TOKEN"] = os.getenv("REPLICATE_API_TOKEN", "")

import replicate

print("🎬 Генерация тестового видео через Veo 3...")
print("Это займёт 1-3 минуты\n")

prompt = "A beautiful woman with long dark hair walks through neon-lit Tokyo streets at night. Cinematic, 4K, rain reflections."

print(f"📝 Prompt: {prompt}")
print("⏳ Отправляю запрос...\n")

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
    print(f"\n✅ УСПЕХ! Видео готово за {elapsed} секунд")
    print(f"📹 URL: {prediction.output}")
else:
    print(f"\n❌ Ошибка: {prediction.status}")
    if prediction.error:
        print(f"Details: {prediction.error}")
