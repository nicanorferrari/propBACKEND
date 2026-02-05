
import os
import sys
from dotenv import load_dotenv
import google.generativeai as genai

# Load root .env
load_dotenv(os.path.join(os.getcwd(), '..', '.env'))

API_KEY = os.getenv("API_KEY")

if not API_KEY:
    print("❌ API_KEY not found in environment.")
    sys.exit(1)

print(f"Testing Gemini API Key...")

try:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content("Hello, this is a connectivity test.")
    
    if response and response.text:
        print("SUCCESS: Gemini API responded correctly.")
        print(f"Response: {response.text}")
    else:
        print("WARNING: Received empty response.")
        
except Exception as e:
    print("ERROR: Connection failed.")
    print(f"Details: {e}")
