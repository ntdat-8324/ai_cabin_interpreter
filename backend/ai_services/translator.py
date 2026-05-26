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

import base64
import json
import httpx
from backend.connection import manager

async def stream_translation(audio_bytes: bytes, draft_text: str, context: str, history: list, chunk_id: str, websocket):
    """
    Sử dụng Gemini 2.5 Flash để dịch thuật, chế độ Streaming.
    """
    if not audio_bytes:
        return ""
        
    base64_audio = base64.b64encode(audio_bytes).decode('utf-8')
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json"
    }

    system_prompt = (
        "Bạn là một thông dịch viên cabin xuất sắc. Dựa vào âm thanh, bản nháp (Draft STT), "
        "lịch sử câu trước và bộ thuật ngữ, hãy dịch câu hiện tại sang ngôn ngữ đích (Anh hoặc Việt) "
        "một cách tự nhiên và chính xác. Trả về đúng bản dịch, không giải thích thêm.\n"
        f"Glossary: {context}\n"
        f"Draft STT: {draft_text}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    
    for item in history:
        messages.append({"role": "user", "content": item["original"]})
        messages.append({"role": "assistant", "content": item["translated"]})

    messages.append({
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "Dịch đoạn audio sau dựa trên Draft STT."
            },
            {
                "type": "input_audio",
                "input_audio": {
                    "data": base64_audio,
                    "format": "webm"
                }
            }
        ]
    })

    payload = {
        "model": "google/gemini-2.5-flash",
        "messages": messages,
        "temperature": 0.0,
        "stream": True
    }

    full_text = ""
    try:
        async with httpx.AsyncClient() as client_httpx:
            async with client_httpx.stream("POST", url, headers=headers, json=payload, timeout=60.0) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data_json = json.loads(data_str)
                            if "choices" in data_json and len(data_json["choices"]) > 0:
                                delta = data_json["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    full_text += content
                                    # Đẩy ngay xuống WebSocket
                                    await manager.send_message_safe(websocket, json.dumps({
                                        "type": "translation",
                                        "chunk_id": chunk_id,
                                        "text": content
                                    }))
                        except Exception as e:
                            pass
        return full_text.strip()
    except Exception as e:
        print(f"[Stream Translation Exception]: {e}")
        return full_text.strip()
