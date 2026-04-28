import google.generativeai as genai

GEMINI_KEY = "AIzaSyAT4Dyp8MjSDq__w2hSHRI6UrY7KHri6s0"
genai.configure(api_key=GEMINI_KEY)

print("--- MODELOS DISPONÍVEIS NA TUA CONTA ---")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"ID: {m.name}")
except Exception as e:
    print(f"Erro ao listar: {e}")