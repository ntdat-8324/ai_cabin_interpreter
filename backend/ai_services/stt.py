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

import json
from backend.connection import manager

async def stream_refined_stt(audio_bytes: bytes, draft_text: str, context: str, history: list, chunk_id: str, websocket):
    """
    Sử dụng Gemini 2.5 Flash để tinh chỉnh lại bản draft STT, chế độ Streaming.
    """
    if not audio_bytes:
        return ""
        
    base64_audio = base64.b64encode(audio_bytes).decode('utf-8')
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json"
    }

    prompt = (
        "Bạn là hệ thống nhận diện giọng nói cực kỳ chính xác. Nhiệm vụ của bạn là nghe đoạn âm thanh hiện tại và tạo ra bản ghi âm gốc (transcript) hoàn hảo nhất.\n"
        "CHỈ THỊ NGHIÊM NGẶT:\n"
        "1. TUYỆT ĐỐI KHÔNG sáng tác hay bịa thêm chữ. Lịch sử câu trước (History) CHỈ được cung cấp để giúp bạn nắm ngữ cảnh, viết đúng chính tả các từ đồng âm (homophones) hoặc tên riêng cho nhất quán.\n"
        "2. Dựa chặt vào bản nháp (Draft STT) và âm thanh thực tế để bám sát sự thật.\n"
        "3. Trả về ĐÚNG câu chữ được nói trong chunk hiện tại, không giải thích gì thêm.\n\n"
        f"Glossary: {context}\n"
    )

    if history:
        history_text = " ".join([item["original"] for item in history])
        prompt += f"Lịch sử câu trước (History): {history_text}\n"

    prompt += f"Bản nháp hiện tại (Draft STT): {draft_text}"

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
                                        "type": "final_stt",
                                        "chunk_id": chunk_id,
                                        "text": content
                                    }))
                        except Exception as e:
                            pass
        return full_text.strip()
    except Exception as e:
        print(f"[Stream Refined STT Exception]: {e}")
        return full_text.strip()
