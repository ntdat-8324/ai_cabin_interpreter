# MASTERPLAN: AI Interpreter PoC (Hệ thống Thông dịch Cabin Tự động)

## 1. Tổng quan Kiến trúc (Architecture Overview)
Dự án nhằm xây dựng một bản Proof of Concept (PoC) cho hệ thống thông dịch viên cabin theo thời gian thực (Anh - Việt / Việt - Anh) dành cho các cuộc họp doanh nghiệp.
Hệ thống chú trọng vào độ trễ thấp (low latency), độ chính xác cao và xử lý luồng dữ liệu (streaming) hoàn toàn trên RAM nhằm tránh nghẽn I/O ổ cứng.

## 2. Luồng dữ liệu (Data Flow)
**[1. Khởi tạo Kết nối]** Frontend thu thập "Meeting Agenda/Glossary" từ người dùng và mở kết nối WebSocket tới Backend, gửi kèm thông tin này trong payload khởi tạo. Backend lưu trữ thông tin này làm Context cho session.
**[2. Thu âm & VAD]** Frontend yêu cầu quyền truy cập Microphone và dùng `MediaRecorder` để thu âm. Thư viện VAD (Voice Activity Detection, vd: hark.js) sẽ phân tích độ lớn âm thanh để phát hiện khoảng lặng (silence). Dựa vào khoảng lặng, luồng thu âm bị ngắt thành các đoạn (chunks), đóng gói thành dữ liệu `.webm` (blob) và gửi lập tức qua WebSocket.
**[3. Nhận Data vào Queue]** Backend nhận các blob âm thanh qua WebSocket. Thay vì ghi ra file, dữ liệu được nạp ngay vào `asyncio.Queue` để không làm chặn luồng nhận dữ liệu của WebSocket.
**[4. Worker Xử lý]** Một Background Task (Worker) ở Backend sẽ lấy các chunk từ Queue, wrap lại bằng `io.BytesIO` để thao tác trực tiếp trên bộ nhớ (RAM).
**[5. Chuyển đổi STT (Speech-to-Text)]** Chunk âm thanh trong `io.BytesIO` cùng với Context (từ bước 1) được gửi qua Groq API (sử dụng model Whisper-large-v3) để chuyển đổi nhanh thành văn bản gốc. Tốc độ nhận diện sẽ đạt mức mili-giây.
**[6. Quản lý Cửa sổ Ngữ cảnh (Sliding Window)]** Văn bản gốc vừa nhận được kết hợp với Lịch sử Dịch thuật (lưu trữ in-memory 2 câu t-1, t-2 gần nhất gồm bản gốc và bản dịch).
**[7. Dịch thuật AI (Translation)]** Cụm dữ liệu (Văn bản hiện tại + Lịch sử + System Instruction nghiêm ngặt về vai trò thông dịch viên cabin) được gọi tới Google Gemini 2.5 Flash Lite API.
**[8. Trả về Kết quả]** Backend nhận bản dịch từ Gemini, cập nhật lại Cửa sổ ngữ cảnh (lưu câu mới t và câu t-1, đẩy câu t-2 ra ngoài). Cuối cùng, Backend trả cả văn bản gốc và bản dịch về Frontend qua WebSocket để hiển thị real-time cho người dùng.

---

## 3. Các Giai đoạn Thực hiện (Phases)

### Phase 1: Setup Môi trường & Cấu trúc thư mục
- **Input:** Yêu cầu dự án PoC.
- **Output:** Môi trường ảo Python chuẩn mực, cấu trúc thư mục dự án được tổ chức rõ ràng. File cấu hình `.env`.
- **Tư duy/Giải quyết (How/Why):** Việc phân tách rành mạch `frontend` và `backend` ngay từ đầu giúp dễ dàng mở rộng sau này. Dùng virtual environment giúp cô lập dependencies. Các khóa API (Groq, Gemini) sẽ được bảo mật trong file `.env`.

### Phase 2: Core Backend & WebSockets
- **Input:** Môi trường đã sẵn sàng.
- **Output:** Server FastAPI có endpoint WebSocket. Các cơ chế như `ConnectionManager`, `asyncio.Queue` và xử lý in-memory byte stream.
- **Tư duy/Giải quyết (How/Why):** FastAPI có hỗ trợ native cực tốt cho `async/await` và WebSocket. Tạo cơ chế Connection Manager để lưu trữ riêng biệt state của từng client (Meeting Context, Sliding Window, Queue). Đảm bảo mọi luồng I/O đều là non-blocking và nằm hoàn toàn trên RAM để đạt tốc độ cabin.

### Phase 3: AI Pipeline Integration
- **Input:** Audio bytes trên RAM, Config Prompt và API Keys.
- **Output:** Modules kết nối thành công với Groq API (cho STT) và Gemini 2.5 Flash Lite API (cho Dịch thuật).
- **Tư duy/Giải quyết (How/Why):** 
  - Tích hợp Whisper qua Groq API để tận dụng LPU cho tốc độ siêu tốc. Truyền tham số `prompt` là Meeting Agenda vào STT.
  - Tích hợp Gemini 2.5 Flash Lite bằng Google GenAI SDK (hoặc LangChain). Thiết lập `System Instruction` cực kỳ chặt chẽ (đóng vai thông dịch, không sinh thêm từ, giữ nguyên tên riêng/số liệu). Lắp ráp pipeline STT -> Xử lý chuỗi -> LLM Translation vào Worker chạy nền đã tạo ở Phase 2.

### Phase 4: Frontend VAD & Client
- **Input:** Template HTML/JS cơ bản, Endpoint WebSocket.
- **Output:** Giao diện Web hiển thị được form cài đặt ngữ cảnh, nút điều khiển (Start/Stop) và kết quả Transcript/Translation dạng cuộn. Luồng gửi audio chuẩn xác.
- **Tư duy/Giải quyết (How/Why):** Để PoC gọn nhẹ, chỉ cần dùng Vanilla JS. Khó nhất ở frontend là cắt chunk âm thanh hợp lý. Sử dụng thư viện VAD (như hark.js) để trigger sự kiện khi người nói tạm dừng, từ đó ra lệnh cho `MediaRecorder` sinh ra Blob ngay lập tức. Việc này giúp STT nhận được một câu trọn vẹn thay vì các mẩu âm thanh bị cắt ngẫu nhiên giữa chừng.

### Phase 5: Testing & Refinement
- **Input:** Các modules ráp nối từ Phase 1 tới 4.
- **Output:** Một hệ thống hoạt động ổn định từ đầu tới cuối (E2E).
- **Tư duy/Giải quyết (How/Why):** Thử nghiệm thông dịch thực tế Anh-Việt và Việt-Anh. Điều chỉnh các tham số quan trọng: Độ nhạy của VAD ở Frontend, nhiệt độ (temperature) của Gemini (đặt bằng 0 hoặc cực thấp để không sáng tạo), và độ dài Sliding Window cho phù hợp với ngữ cảnh thực tế.
