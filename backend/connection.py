import asyncio
from fastapi import WebSocket
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        # Mapping WebSocket tới Queue chứa Audio Chunks
        self.audio_queues: dict[WebSocket, asyncio.Queue] = {}
        # Mapping WebSocket tới Context (Agenda, Sliding Window History)
        self.contexts: dict[WebSocket, dict] = {}

    def connect(self, websocket: WebSocket, context_data: dict):
        self.active_connections.append(websocket)
        self.audio_queues[websocket] = asyncio.Queue()
        self.contexts[websocket] = {
            "agenda": context_data.get("agenda", ""),
            "raw_agenda": context_data.get("raw_agenda", ""),
            "history": [] # Lưu 2 câu gần nhất: [{"original": "...", "translated": "..."}]
        }

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.audio_queues:
            del self.audio_queues[websocket]
        if websocket in self.contexts:
            del self.contexts[websocket]

    def get_queue(self, websocket: WebSocket) -> asyncio.Queue | None:
        return self.audio_queues.get(websocket)

    async def send_result(self, websocket: WebSocket, original: str, translated: str):
        data = {
            "original": original,
            "translated": translated
        }
        await websocket.send_text(json.dumps(data))

manager = ConnectionManager()
