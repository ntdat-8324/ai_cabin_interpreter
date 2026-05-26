import os
import re
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# Khởi tạo OpenRouter Client (Sử dụng SDK của OpenAI)
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY")
)

async def translate_text(transcript_whisper: str, transcript_gemini: str, context_agenda: str, history: list) -> str:
    """
    Sử dụng OpenRouter để gộp 2 bản STT và dịch cực nhanh.
    Chỉ trả về chuỗi văn bản (không dùng JSON để tiết kiệm thời gian generate token).
    """
    if not transcript_whisper and not transcript_gemini:
        return ""
        
    system_prompt = (
        "You are an expert Cabin Interpreter. "
        "You will receive 2 STT variants (Whisper and Gemini) of the SAME audio chunk. "
        "Task: "
        "1. Identify the true spoken content. "
        "2. Translate it into English or Vietnamese (depending on the source language). "
        "3. Output ONLY the translated text. DO NOT output JSON. DO NOT add explanations."
        f"\nMeeting Glossary/Context: {context_agenda}"
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    
    for item in history:
        # Lịch sử dịch thuật để giữ context
        messages.append({"role": "user", "content": item["original"]})
        messages.append({"role": "assistant", "content": item["translated"]})
        
    current_input = f"Variant 1: {transcript_whisper}\nVariant 2: {transcript_gemini}"
    messages.append({"role": "user", "content": current_input})
    
    try:
        response = await client.chat.completions.create(
            model="google/gemini-2.5-flash",
            messages=messages,
            temperature=0.0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Translation Error]: {e}")
        return ""
