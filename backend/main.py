from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from backend.connection import manager
from backend.worker import process_audio_queue
import json
import asyncio

app = FastAPI(title="AI Interpreter API")

# Cấu hình CORS để Frontend (chạy file local hoặc port khác) có thể truy cập
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "AI Interpreter Backend is running."}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    worker_task = None
    
    try:
        # 1. Handshake: Nhận config context đầu tiên (JSON)
        init_message = await websocket.receive_text()
        context_data = json.loads(init_message)
        raw_agenda = context_data.get('agenda', '')
        print(f"[+] Client mới kết nối. Context Agenda: '{raw_agenda}'")
        
        # Tiền xử lý Context
        from backend.ai_services.context_processor import summarize_context
        print("[*] Đang tóm tắt Context...")
        summarized_agenda = await summarize_context(raw_agenda)
        print(f"[*] Context đã tóm tắt: {summarized_agenda}")
        
        context_data['raw_agenda'] = raw_agenda
        context_data['agenda'] = summarized_agenda
        
        # Đăng ký kết nối vào ConnectionManager
        manager.connect(websocket, context_data)
        
        # Khởi chạy Background Worker để xử lý luồng Audio riêng biệt cho client này
        worker_task = asyncio.create_task(process_audio_queue(websocket))
        
        # 2. Vòng lặp nhận dữ liệu Audio (Binary)
        while True:
            data = await websocket.receive_bytes()
            print(f"[Audio] Nhận chunk audio có kích thước: {len(data)} bytes")
            
            # Đẩy dữ liệu vào Queue xử lý
            queue = manager.get_queue(websocket)
            if queue is not None:
                await queue.put(data)
                
    except WebSocketDisconnect:
        print("[-] Client đã ngắt kết nối.")
    except Exception as e:
        print(f"[!] Lỗi WebSocket: {e}")
    finally:
        # Dọn dẹp Worker và Connection
        if worker_task:
            worker_task.cancel()
        manager.disconnect(websocket)
