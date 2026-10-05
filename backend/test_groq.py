from app.config import settings
from openai import OpenAI

client = OpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)
print(f"Key length: {len(settings.LLM_API_KEY)}, Model: {settings.LLM_MODEL}")

try:
    r = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[{"role": "user", "content": 'Reply with JSON only: {"greeting": "hello"}'}],
        temperature=0,
        timeout=30,
    )
    print("LLM OK:", r.choices[0].message.content[:200])
except Exception as e:
    print(f"LLM ERROR: {type(e).__name__}: {str(e)[:400]}")
