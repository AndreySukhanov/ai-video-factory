import os
from dotenv import load_dotenv
load_dotenv()

token = os.getenv("REPLICATE_API_TOKEN", "")
print(f"Token: {token[:15]}...{token[-5:]}" if token else "❌ No token!")

if token:
    os.environ["REPLICATE_API_TOKEN"] = token
    try:
        import replicate
        model = replicate.models.get("google/veo-3-fast")
        print(f"✅ Replicate connected!")
        print(f"Model: {model.name}")
    except Exception as e:
        print(f"❌ Error: {e}")
