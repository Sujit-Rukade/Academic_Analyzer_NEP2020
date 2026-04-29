from google import genai

# Pass your specific API key here
client = genai.Client(api_key="AIzaSyDMAmLuHdUUt-c3Zxxj9pi0xPLEHl9OV8c")

print("Available models:")
for m in client.models.list():
    print(m.name)