from google import genai

client = genai.Client(api_key="AIzaSyD4Xk2UATqUBf6kOzNtcH5O3-oDb1ZQt_k")

response = client.models.generate_content(
    model="gemini-2.0-flash-exp",
    contents="Hello Gemini! How are you?"
)

print(response.candidates[0].content.parts[0].text)
