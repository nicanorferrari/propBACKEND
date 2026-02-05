
import os
import sys
from dotenv import load_dotenv
import google.generativeai as genai

# Load root .env
load_dotenv(os.path.join(os.getcwd(), '..', '.env'))

API_KEY = os.getenv("API_KEY")

if not API_KEY:
    print("API_KEY not found.")
    sys.exit(1)

print("Test: Embedding generation...")
genai.configure(api_key=API_KEY)

try:
    result = genai.embed_content(
        model="models/text-embedding-004",
        content="Prueba de embedding",
        task_type="retrieval_document"
    )
    print("SUCCESS: Embedding generated!")
    print(f"Vector length: {len(result['embedding'])}")
except Exception as e:
    print("ERROR: Embedding Failed.")
    print("------------------------------------------------")
    print(e)
    print("------------------------------------------------")
