import requests

url = "http://127.0.0.1:5000/chat"
query = {"message": "What is the latest iPhone released by Apple in 2025?"}
response = requests.post(url, json=query)

print("Bot:", response.json()["reply"])
