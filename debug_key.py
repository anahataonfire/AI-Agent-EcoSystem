
import os
from dotenv import load_dotenv

load_dotenv(override=True)
key = os.environ.get("GOOGLE_API_KEY", "")

print(f"Loaded from: {os.path.abspath('.env')}")
print(f"Key length: {len(key)}")
if len(key) > 10:
    print(f"Key starts with: {key[:5]}...")
    print(f"Key ends with: ...{key[-5:]}")
else:
    print("Key is too short or empty")
