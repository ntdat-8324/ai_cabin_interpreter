import asyncio
# pyrefly: ignore [missing-import]
from fastapi import WebSocket
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        # Mapping WebSocket tới Queue chứa Audio Chunks
        self.audio_queues: dict[WebSocket, asyncio.Queue] = {}
        # Mapping WebSocket tới Context (Agenda, Sliding Window History)
        self.contexts: dict[WebSocket, dict] = {}
        # Lock để chống đụng độ khi stream
        self.locks: dict[WebSocket, asyncio.Lock] = {}

    def connect(self, websocket: WebSocket, context_data: dict):
        self.active_connections.append(websocket)
        self.audio_queues[websocket] = asyncio.Queue()
        self.contexts[websocket] = {
            "agenda": context_data.get("agenda", ""),
            "raw_agenda": context_data.get("raw_agenda", ""),
            "history": [] # Lưu 2 câu gần nhất: [{"original": "...", "translated": "..."}]
        }
        self.locks[websocket] = asyncio.Lock()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.audio_queues:
            del self.audio_queues[websocket]
        if websocket in self.contexts:
            del self.contexts[websocket]
        if websocket in self.locks:
            del self.locks[websocket]

    def get_queue(self, websocket: WebSocket) -> asyncio.Queue | None:
        return self.audio_queues.get(websocket)

    async def send_result(self, websocket: WebSocket, original: str, translated: str):
        data = {
            "original": original,
            "translated": translated
        }
        await self.send_message_safe(websocket, json.dumps(data))

    async def send_message_safe(self, websocket: WebSocket, message: str):
        lock = self.locks.get(websocket)
        if lock:
            async with lock:
                await websocket.send_text(message)

manager = ConnectionManager()
