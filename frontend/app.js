let ws;
let mediaRecorder;
let audioChunks = [];
let stream;

// VAD (Voice Activity Detection) Variables
let audioContext;
let analyser;
let microphone;
let isSpeaking = false;
let silenceTimer;
const SILENCE_DELAY = 1200; // Đợi 1.2s im lặng thì ngắt câu
const SPEAKING_THRESHOLD = 10; // Phục hồi độ nhạy để không bị miss từ (bỏ lỡ giọng nói)

// UI Elements
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const uploadBtn = document.getElementById('uploadBtn');
const audioUpload = document.getElementById('audioUpload');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const originalBox = document.getElementById('originalBox');
const translatedBox = document.getElementById('translatedBox');

function getOrCreateMessageContainer(box, chunkId, isTranslation=false) {
    let div = document.getElementById(`chunk-${chunkId}-${isTranslation ? 'trans' : 'orig'}`);
    if (!div) {
        div = document.createElement('div');
        div.id = `chunk-${chunkId}-${isTranslation ? 'trans' : 'orig'}`;
        div.className = `message ${isTranslation ? 'translation-msg' : 'original-msg'}`;
        box.appendChild(div);
        
        while (box.children.length > 5) {
            box.removeChild(box.firstChild);
        }
    }
    box.scrollTop = box.scrollHeight;
    return div;
}

function updateStatus(text, state) {
    statusText.textContent = text;
    if(state === 'listening') {
        statusDot.classList.add('pulse');
        statusDot.style.backgroundColor = 'var(--success)';
    } else if (state === 'processing') {
        statusDot.classList.remove('pulse');
        statusDot.style.backgroundColor = 'var(--warning)';
    } else {
        statusDot.classList.remove('pulse');
        statusDot.style.backgroundColor = 'var(--text-secondary)';
    }
}

// Bắt đầu luồng VAD bằng Web Audio API
function startVAD(stream) {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        analyser.minDecibels = -70;
        analyser.smoothingTimeConstant = 0.2;
        analyser.fftSize = 512;
        
        microphone = audioContext.createMediaStreamSource(stream);
        microphone.connect(analyser);
    }
    
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    
    function checkAudioLevel() {
        if (!audioContext) return;
        analyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
            sum += dataArray[i];
        }
        let average = sum / bufferLength;
        
        if (average > SPEAKING_THRESHOLD) { 
            // Nếu phát hiện có tiếng nói
            if (!isSpeaking) {
                isSpeaking = true;
                onSpeakingStart();
            }
            // Reset lại bộ đếm im lặng
            clearTimeout(silenceTimer);
            silenceTimer = setTimeout(() => {
                if(isSpeaking) {
                    isSpeaking = false;
                    onSpeakingStop();
                }
            }, SILENCE_DELAY);
        }
        
        requestAnimationFrame(checkAudioLevel);
    }
    checkAudioLevel();
}

function onSpeakingStart() {
    updateStatus("Listening...", 'listening');
    // Khởi tạo MediaRecorder MỚI cho CÂU NÀY. 
    // Điều này đảm bảo chunk tạo ra là 1 file WebM hoàn chỉnh có chứa Header.
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    audioChunks = [];
    
    mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
            audioChunks.push(event.data);
        }
    };
    
    mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        if(ws && ws.readyState === WebSocket.OPEN && audioBlob.size > 0) {
            console.log(`[VAD] Gửi câu nói (size: ${audioBlob.size} bytes)`);
            chunkStartTimes.push(Date.now()); // Ghi nhận thời gian bắt đầu gửi lên Backend
            ws.send(audioBlob);
        }
    };
    
    mediaRecorder.start();
}

let chunkStartTimes = []; // Hàng đợi lưu thời điểm ngắt chunk

function onSpeakingStop() {
    updateStatus("Processing...", 'processing');
    if(mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
    }
    setTimeout(() => {
        if(!isSpeaking) updateStatus("Waiting for speech...", 'idle');
    }, 500);
}

startBtn.addEventListener('click', async () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
    }
    const agenda = document.getElementById('agendaInput').value;
    
    ws = new WebSocket('ws://localhost:8000/ws');
    
    ws.onopen = async () => {
        console.log("WebSocket: Connected");
        ws.send(JSON.stringify({ agenda: agenda }));
        
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            startBtn.classList.add('hidden');
            if (uploadBtn) uploadBtn.classList.add('hidden');
            stopBtn.classList.remove('hidden');
            updateStatus("Waiting for speech...", 'idle');
            
            startVAD(stream);
        } catch (err) {
            console.error("Lỗi Microphone:", err);
            alert("Không thể truy cập Microphone!");
            ws.close();
        }
    };
    setupWsHandlers();
});

if (uploadBtn) {
    uploadBtn.addEventListener('click', () => {
        audioUpload.click();
    });
}

if (audioUpload) {
    audioUpload.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.close();
        }

        const agenda = document.getElementById('agendaInput').value;
        ws = new WebSocket('ws://localhost:8000/ws');
        
        ws.onopen = async () => {
            console.log("WebSocket: Connected (File Upload)");
            ws.send(JSON.stringify({ agenda: agenda }));
            
            startBtn.classList.add('hidden');
            uploadBtn.classList.add('hidden');
            stopBtn.classList.remove('hidden');
            updateStatus("Simulating live audio...", 'listening');
            
            const audioUrl = URL.createObjectURL(file);
            const audioEl = new Audio(audioUrl);
            audioEl.crossOrigin = "anonymous";
            
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            analyser = audioContext.createAnalyser();
            analyser.minDecibels = -70;
            analyser.smoothingTimeConstant = 0.2;
            analyser.fftSize = 512;
            
            const source = audioContext.createMediaElementSource(audioEl);
            source.connect(analyser);
            analyser.connect(audioContext.destination);
            
            if (audioEl.captureStream) {
                stream = audioEl.captureStream();
            } else if (audioEl.mozCaptureStream) {
                stream = audioEl.mozCaptureStream();
            } else {
                const dest = audioContext.createMediaStreamDestination();
                source.connect(dest);
                stream = dest.stream;
            }
            
            startVAD(stream);
            audioEl.play();
            
            audioEl.onended = () => {
                stopRecording();
                updateStatus("Finished audio file", 'idle');
            };
        };
        setupWsHandlers();
    });
}

function setupWsHandlers() {
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === "draft") {
            const origContainer = getOrCreateMessageContainer(originalBox, data.chunk_id, false);
            origContainer.textContent = data.text + " ⚡";
            origContainer.classList.add('draft-text');
            
            const transContainer = getOrCreateMessageContainer(translatedBox, data.chunk_id, true);
            transContainer.innerHTML = '<span class="draft-text">...</span>';
        } 
        else if (data.type === "final_stt") {
            const origContainer = getOrCreateMessageContainer(originalBox, data.chunk_id, false);
            if (origContainer.classList.contains('draft-text')) {
                origContainer.classList.remove('draft-text');
                origContainer.textContent = '';
            }
            origContainer.textContent += data.text;
        }
        else if (data.type === "translation") {
            const transContainer = getOrCreateMessageContainer(translatedBox, data.chunk_id, true);
            if (transContainer.querySelector('.draft-text')) {
                transContainer.innerHTML = '';
            }
            transContainer.textContent += data.text;
        }
    };
    
    ws.onclose = () => {
        console.log("WebSocket: Disconnected");
    };
    
    ws.onerror = (e) => {
        console.error("WebSocket Error:", e);
    }
}

stopBtn.addEventListener('click', stopRecording);

function stopRecording() {
    if(mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
    }

    if (stream) {
        stream.getTracks().forEach(t => t.stop());
    }
    
    // Lưu ý: KHÔNG đóng WebSocket ở đây để các task AI đang chạy ở Backend 
    // vẫn có thể stream kết quả cuối cùng về UI.
    
    if(audioContext) {
        audioContext.close();
        audioContext = null;
    }
    clearTimeout(silenceTimer);
    isSpeaking = false;
    
    startBtn.classList.remove('hidden');
    if (uploadBtn) uploadBtn.classList.remove('hidden');
    stopBtn.classList.add('hidden');
    updateStatus("Idle (Waiting for pending results...)", 'idle');
}
