from serpapi import GoogleSearch

search = GoogleSearch({
    "q": "OpenAI",
    "engine": "google",
    "api_key": "cada52aecb752591dca45f8a7f25c5c960c302727047b589c253f032653758b2"
})

results = search.get_dict()
print(results)