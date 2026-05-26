import asyncio
import json
from backend.connection import manager
from backend.ai_services.stt import transcribe_audio, transcribe_audio_gemini
from backend.ai_services.translator import translate_text

async def translation_worker(websocket, text_queue, context):
    """
    Worker 2: Chuyên trách Dịch thuật (Consumer của Text Queue).
    """
    while True:
        try:
            data = await text_queue.get()
            transcript_whisper = data['whisper']
            transcript_gemini = data['gemini']
            raw_agenda = context.get("raw_agenda", "")
            history = context.get("trans_history", [])
            
            print("[Trans Worker] 🌐 Đang gộp và dịch thuật...")
            translation = await translate_text(
                transcript_whisper=transcript_whisper,
                transcript_gemini=transcript_gemini,
                context_agenda=raw_agenda,
                history=history
            )
            
            best_original = data['preview']
            
            if translation:
                history.append({"original": best_original, "translated": translation})
                if len(history) > 2:
                    history.pop(0)
                
                await websocket.send_text(json.dumps({
                    "translated": translation
                }))
                print(f"[Trans Result] => {translation}")
                
            text_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[!] Trans Worker Error: {e}")

async def process_audio_queue(websocket):
    """
    Worker 1: Chuyên trách STT
    """
    audio_queue = manager.get_queue(websocket)
    context = manager.contexts.get(websocket)
    
    if not audio_queue or not context:
        return
        
    text_queue = asyncio.Queue()
    trans_task = asyncio.create_task(translation_worker(websocket, text_queue, context))
    
    context['stt_history'] = []
    context['trans_history'] = []
    
    while True:
        try:
            audio_bytes = await audio_queue.get()
            agenda = context.get("agenda", "")
            
            print("[STT Worker] 🎤 Đang chạy Dual STT...")
            
            # Tạo Task chạy song song
            task_whisper = asyncio.create_task(transcribe_audio(audio_bytes, prompt_context=agenda))
            task_gemini = asyncio.create_task(transcribe_audio_gemini(audio_bytes, summarized_context=agenda, history=context['stt_history']))
            
            # 🚀 SIÊU TỐC: Đợi Groq Whisper (thường < 0.5s) xong là bắn lên màn hình luôn! Không chờ Gemini
            transcript_whisper = await task_whisper
            
            if transcript_whisper:
                await websocket.send_text(json.dumps({"original": transcript_whisper}))
                context['stt_history'].append({"original": transcript_whisper})
                if len(context['stt_history']) > 2:
                    context['stt_history'].pop(0)
            
            # Nhẩn nha chờ Gemini STT nốt (thường 2-3s) để làm nguyên liệu dịch thuật (Dual STT)
            transcript_gemini = await task_gemini
            
            if not transcript_whisper and not transcript_gemini:
                audio_queue.task_done()
                continue
            
            await text_queue.put({
                'whisper': transcript_whisper,
                'gemini': transcript_gemini,
                'preview': transcript_whisper if transcript_whisper else transcript_gemini
            })
            
            audio_queue.task_done()
            
        except asyncio.CancelledError:
            trans_task.cancel()
            break
        except Exception as e:
            print(f"[!] STT Worker Error: {e}")
