import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

print("Available models:")
for m in genai.list_models():
    print("-", m.name)

model = genai.GenerativeModel("gemini-1.5-flash")
response = model.generate_content("Hello! Tell me something interesting about AI.")
print("Response:", response.text)
