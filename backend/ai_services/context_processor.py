import os
from openai import AsyncOpenAI

# Khởi tạo OpenRouter Client
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY")
)

async def summarize_context(raw_context: str) -> str:
    """
    Sử dụng Gemini qua OpenRouter để tóm tắt và trích xuất thực thể từ Raw Context.
    Kết quả không quá 150 chữ.
    """
    if not raw_context or len(raw_context.strip()) < 10:
        return raw_context

    system_prompt = (
        "You are an expert at information extraction. The user will provide a raw meeting agenda or context. "
        "Your task is to summarize it and extract key entities (names, acronyms, specific terms) that an STT system "
        "should look out for. The output must be concise, act as a glossary/prompt, and STRICTLY under 150 words. "
        "Just return the summary text."
    )
    
    try:
        response = await client.chat.completions.create(
            model="google/gemini-2.5-flash-lite",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_context}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Context Summarize Error]: {e}")
        return raw_context # Fallback to raw if error
