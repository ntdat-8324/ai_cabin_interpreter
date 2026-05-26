# AI Cabin Interpreter (Proof of Concept)

## 📖 1. What is this tool? (For Non-Technical Users)
The **AI Cabin Interpreter** is a real-time translation system designed for international meetings. It acts just like a human cabin interpreter: you speak into your microphone in English or Vietnamese, and the system instantly transcribes and translates your speech into the other language, displaying it on the screen. 

Instead of waiting for you to finish a long speech, it intelligently detects when you pause and translates chunk-by-chunk to keep the conversation flowing naturally.

### Limitations
- **Background Noise Sensitivity:** The system uses microphone volume to detect when you start and stop speaking. Loud background noises might trigger the system accidentally.
- **Chunk-based Delay:** To ensure high translation quality, the AI waits for a complete phrase or sentence before translating, resulting in a slight 1-2 second delay compared to word-by-word transcription.
- **API Dependencies:** Requires stable internet and active API keys for Groq and OpenRouter (Gemini).

---

## 🚀 2. How to Run It

### Prerequisites
- Python 3.9+
- A modern web browser (Chrome/Edge/Firefox)

### Setup Steps
1. **Clone the repository** and navigate to the project folder.
2. **Install backend dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure API Keys:**
   - Copy `.env.example` to `.env`.
   - Fill in your `GROQ_API_KEY` (for fast Speech-to-Text) and `OPENROUTER_API_KEY` (for Gemini 2.5 Flash translation).
4. **Start the Backend Server:**
   ```bash
   uvicorn backend.main:app --reload
   ```
5. **Launch the Frontend:**
   - Simply double-click on `frontend/index.html` to open it in your web browser.
   - Enter your meeting agenda/context, click **Start Translation**, allow microphone access, and start speaking!

---

## 🧠 3. Developer's Agentic Coding Journey (Submission Details)

### AI in the Development Process
This project was developed with a deeply agentic, AI-assisted workflow. Instead of just using AI as a sophisticated autocomplete, AI agents were utilized to **architect the system, design the in-memory data flow, and structure the asynchronous workers**. 

The process involved collaborative brainstorming to solve a critical issue: *How do we achieve cabin-interpreter-level latency without complex, heavy streaming architectures?* The AI helped formulate the architecture of using Vanilla JS AudioContext for VAD (Voice Activity Detection) on the frontend, paired with an `asyncio.Queue` WebSocket backend to keep all byte processing entirely on RAM.

### Techniques, Libraries, and Tools Used
- **Prompt Chaining & Context Injection:** The system utilizes a specialized prompt chain. First, a lightweight LLM call summarizes the user's "Meeting Agenda". This summary is then injected dynamically into the Groq Whisper STT prompt to guide its vocabulary (e.g., catching specific acronyms). Finally, the transcription and context are chained into the Translation LLM prompt.
- **Multi-Model Orchestration:** The backend orchestrates different models for different strengths. It uses **Groq's Whisper-large-v3** for blazing-fast Speech-to-Text (delivering results in milliseconds), and **Google's Gemini 2.5 Flash Lite** (via OpenRouter) for context summarization and high-quality, strict translation.
- **In-Memory Streaming (No Disk I/O):** Audio blobs sent over WebSockets are wrapped in `io.BytesIO` and processed directly in memory by asynchronous workers, entirely bypassing disk read/write bottlenecks.

### Why this approach is better than baselines
* **The Baseline:** Standard transcription setups either record a whole audio file before processing (too slow) or use expensive, complex continuous streaming APIs (overkill for a PoC).
* **Our Approach:** By building a custom VAD in the browser, we intelligently chunk audio based on natural speech pauses and stream them instantly. This provides a near-real-time experience while allowing the LLM to have enough context (a full phrase) to perform a *grammatically correct* translation—something word-by-word streaming struggles with.

### Trade-offs Made
- **Chunking vs. Continuous Streaming:** We traded continuous word-by-word streaming for "chunk-based" streaming. While word-by-word feels faster, it lacks grammatical context, leading to poor translations. Waiting for a pause ensures the LLM sees the whole sentence structure, sacrificing a fraction of a second for vastly superior translation accuracy.
- **Vanilla JS VAD vs. ML VAD:** To keep the frontend lightweight and dependency-free, we used basic volume-threshold VAD via the Web Audio API rather than a heavy Machine Learning VAD model (like Silero VAD).

### What I would do differently with more time
1. **WebRTC Integration:** Replace WebSockets with WebRTC for the audio transport layer to shave off a few more milliseconds of latency and handle packet loss better.
2. **Text-to-Speech (TTS):** Pipe the translated text back into an ultra-low latency TTS model (like ElevenLabs or Cartesia) so the user can hear the translated voice, completing the "cabin interpreter" loop.
3. **Advanced VAD:** Integrate WebRTC VAD into the frontend to better filter out background noise instead of relying purely on decibel levels.
