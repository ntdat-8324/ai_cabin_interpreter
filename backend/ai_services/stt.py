import os
import io
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

# Khởi tạo Groq Client
client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))

async def transcribe_audio(audio_bytes: bytes, prompt_context: str = "") -> str:
    """
    Sử dụng Groq API (Whisper-large-v3) để chuyển đổi byte audio sang văn bản.
    """
    if not audio_bytes:
        return ""
        
    # Wrap byte array thành file-like object để thư viện Groq có thể đọc
    file_obj = io.BytesIO(audio_bytes)
    file_obj.name = "audio.webm" # Groq API yêu cầu có tên file với phần mở rộng
    
    try:
        transcription = await client.audio.transcriptions.create(
            file=(file_obj.name, file_obj.read()),
            model="whisper-large-v3",
            prompt=prompt_context, # Tiêm Agenda làm context để Whisper nhận diện tốt hơn
            response_format="text",
            temperature=0.0
        )
        return transcription.strip()
    except Exception as e:
        print(f"[STT Error]: {e}")
        return ""

import base64
import httpx

async def transcribe_audio_gemini(audio_bytes: bytes, summarized_context: str, history: list) -> str:
    """
    Sử dụng Gemini 2.5 Flash Lite qua OpenRouter để STT âm thanh dạng Base64.
    """
    if not audio_bytes:
        return ""
        
    base64_audio = base64.b64encode(audio_bytes).decode('utf-8')
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json"
    }

    # BỎ HOÀN TOÀN history và context khỏi prompt của STT để cắt đứt "nguồn nguyên liệu" gây ảo giác.
    # LLM sẽ không biết đây là cuộc họp Townhall, không có từ khóa -> bắt buộc phải tập trung nghe Audio.
    prompt = (
        "You are a strict Automatic Speech Recognition (ASR) system. "
        "Your ONLY task is to return the EXACT words spoken in this short audio clip. "
        "If it is just noise, silence, or you cannot hear clear words, return an EMPTY string. "
        "Output ONLY the transcribed text without any formatting."
    )

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": base64_audio,
                        "format": "webm"
                    }
                }
            ]
        }
    ]

    payload = {
        "model": "google/gemini-2.5-flash",
        "messages": messages,
        "temperature": 0.0
    }

    try:
        async with httpx.AsyncClient() as client_httpx:
            response = await client_httpx.post(url, headers=headers, json=payload, timeout=60.0)
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"].strip()
            else:
                print(f"[Gemini STT Error]: {data}")
                return ""
    except Exception as e:
        print(f"[Gemini STT Exception]: {e}")
        return ""
