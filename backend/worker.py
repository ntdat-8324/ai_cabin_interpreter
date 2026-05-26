import asyncio
import json
import uuid
from backend.connection import manager
from backend.ai_services.stt import transcribe_audio, stream_refined_stt
from backend.ai_services.translator import stream_translation

async def process_audio_queue(websocket):
    """
    Worker xử lý Audio theo mô hình Cascading Parallel Multimodal Streaming.
    """
    audio_queue = manager.get_queue(websocket)
    context = manager.contexts.get(websocket)
    
    if not audio_queue or not context:
        return
        
    while True:
        try:
            audio_bytes = await audio_queue.get()
            agenda = context.get("agenda", "")
            history = context.get("history", [])
            
            # 1. Luồng STT Siêu tốc (Bản nháp)
            print("[Worker] 🎤 Đang lấy bản nháp STT từ Whisper...")
            draft_text = await transcribe_audio(audio_bytes, prompt_context=agenda)
            
            if not draft_text:
                audio_queue.task_done()
                continue

            chunk_id = str(uuid.uuid4())
            
            # Gửi Draft Text xuống UI ngay lập tức
            await manager.send_message_safe(websocket, json.dumps({
                "type": "draft",
                "chunk_id": chunk_id,
                "text": draft_text
            }))
            
            # 2. Phân luồng Song song (Parallel Multimodal Streaming)
            print("[Worker] 🌐 Đang stream song song Refined STT và Translation...")
            
            task_stt = asyncio.create_task(stream_refined_stt(
                audio_bytes=audio_bytes,
                draft_text=draft_text,
                context=agenda,
                history=history,
                chunk_id=chunk_id,
                websocket=websocket
            ))
            
            task_trans = asyncio.create_task(stream_translation(
                audio_bytes=audio_bytes,
                draft_text=draft_text,
                context=agenda,
                history=history,
                chunk_id=chunk_id,
                websocket=websocket
            ))
            
            # Chờ cả 2 luồng hoàn thành
            final_stt, final_translation = await asyncio.gather(task_stt, task_trans)
            
            # Cập nhật History
            if final_stt and final_translation:
                history.append({
                    "original": final_stt,
                    "translated": final_translation
                })
                # Chỉ giữ 2 câu gần nhất
                if len(history) > 2:
                    history.pop(0)
            
            audio_queue.task_done()
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[!] Worker Error: {e}")
