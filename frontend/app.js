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
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const originalBox = document.getElementById('originalBox');
const translatedBox = document.getElementById('translatedBox');

function appendMessage(box, text, isTranslation=false) {
    const div = document.createElement('div');
    div.className = `message ${isTranslation ? 'translation-msg' : 'original-msg'}`;
    div.textContent = text;
    box.appendChild(div);
    
    // Giới hạn UI chỉ giữ lại tối đa 3 kết quả mới nhất
    while (box.children.length > 3) {
        box.removeChild(box.firstChild);
    }
    
    box.scrollTop = box.scrollHeight; // Auto scroll to bottom
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
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    analyser.minDecibels = -70;
    analyser.smoothingTimeConstant = 0.2;
    analyser.fftSize = 512;
    
    microphone = audioContext.createMediaStreamSource(stream);
    microphone.connect(analyser);
    
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
    const agenda = document.getElementById('agendaInput').value;
    
    ws = new WebSocket('ws://localhost:8000/ws');
    
    ws.onopen = async () => {
        console.log("WebSocket: Connected");
        ws.send(JSON.stringify({ agenda: agenda }));
        
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            startBtn.classList.add('hidden');
            stopBtn.classList.remove('hidden');
            updateStatus("Waiting for speech...", 'idle');
            
            // Override hàm onstop của MediaRecorder trong startVAD để lưu timestamp
            const originalStartVAD = startVAD;
            
            startVAD(stream);
            
        } catch (err) {
            console.error("Lỗi Microphone:", err);
            alert("Không thể truy cập Microphone!");
            ws.close();
        }
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if(data.original) {
             // Thời gian từ lúc gửi chunk đến khi có kết quả STT đầu tiên
             let t0 = chunkStartTimes.length > 0 ? chunkStartTimes[0] : Date.now();
             let sttLatency = ((Date.now() - t0) / 1000).toFixed(2);
             appendMessage(originalBox, `${data.original} ⚡ ${sttLatency}s`, false);
        }
        
        if(data.translated) {
             // Thời gian từ lúc gửi chunk đến khi hoàn tất dịch thuật (End-to-End)
             let t0 = chunkStartTimes.length > 0 ? chunkStartTimes.shift() : Date.now();
             let totalLatency = ((Date.now() - t0) / 1000).toFixed(2);
             appendMessage(translatedBox, `${data.translated} ⚡ ${totalLatency}s`, true);
        }
    }

    
    ws.onclose = () => {
        console.log("WebSocket: Disconnected");
        stopRecording();
    };
    
    ws.onerror = (e) => {
        console.error("WebSocket Error:", e);
    }
});

stopBtn.addEventListener('click', stopRecording);

function stopRecording() {
    if (stream) {
        stream.getTracks().forEach(t => t.stop());
    }
    if (ws) {
        ws.close();
    }
    if(audioContext) {
        audioContext.close();
        audioContext = null;
    }
    clearTimeout(silenceTimer);
    isSpeaking = false;
    
    startBtn.classList.remove('hidden');
    stopBtn.classList.add('hidden');
    updateStatus("Idle", 'idle');
}
