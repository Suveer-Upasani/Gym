class DeadliftAnalyzer {
    constructor() {
        this.isAnalyzing = false;
        this.videoStream = null;
        this.analysisInterval = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.startDataPolling();
    }

    bindEvents() {
        document.getElementById('startBtn').addEventListener('click', () => this.toggleAnalysis());
        document.getElementById('resetBtn').addEventListener('click', () => this.resetSession());
    }

    async toggleAnalysis() {
        const startBtn = document.getElementById('startBtn');
        
        if (!this.isAnalyzing) {
            try {
                this.videoStream = await navigator.mediaDevices.getUserMedia({ 
                    video: { 
                        width: { ideal: 640 },
                        height: { ideal: 480 },
                        facingMode: 'environment' 
                    } 
                });
                
                this.isAnalyzing = true;
                startBtn.textContent = 'STOP ANALYSIS';
                startBtn.classList.add('analyzing');
                
                this.startFrameCapture();
                
            } catch (error) {
                console.error('Error accessing camera:', error);
                alert('Unable to access camera. Please ensure you have granted camera permissions.');
            }
        } else {
            this.stopAnalysis();
            startBtn.textContent = 'START ANALYSIS';
            startBtn.classList.remove('analyzing');
        }
    }

    startFrameCapture() {
        const video = document.createElement('video');
        video.srcObject = this.videoStream;
        video.play();
        
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        this.analysisInterval = setInterval(() => {
            if (video.readyState === video.HAVE_ENOUGH_DATA) {
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                ctx.drawImage(video, 0, 0);
                
                const frameData = canvas.toDataURL('image/jpeg', 0.7);
                this.sendFrameToServer(frameData);
            }
        }, 100); // 10 FPS to reduce server load
    }

    async sendFrameToServer(frameData) {
        try {
            const response = await fetch('/upload_frame', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ frame: frameData })
            });
            
            if (!response.ok) {
                throw new Error('Server error');
            }
        } catch (error) {
            console.error('Error sending frame:', error);
        }
    }

    async resetSession() {
        try {
            const response = await fetch('/reset_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                this.updateUI();
            }
        } catch (error) {
            console.error('Error resetting session:', error);
        }
    }

    stopAnalysis() {
        this.isAnalyzing = false;
        
        if (this.analysisInterval) {
            clearInterval(this.analysisInterval);
            this.analysisInterval = null;
        }
        
        if (this.videoStream) {
            this.videoStream.getTracks().forEach(track => track.stop());
            this.videoStream = null;
        }
    }

    startDataPolling() {
        setInterval(() => {
            this.fetchAnalysisData();
            this.fetchRepHistory();
        }, 1000); // Update every second
    }

    async fetchAnalysisData() {
        try {
            const response = await fetch('/analysis_data');
            const data = await response.json();
            this.updateUI(data);
        } catch (error) {
            console.error('Error fetching analysis data:', error);
        }
    }

    async fetchRepHistory() {
        try {
            const response = await fetch('/rep_history');
            const history = await response.json();
            this.updateHistoryUI(history);
        } catch (error) {
            console.error('Error fetching rep history:', error);
        }
    }

    updateUI(data) {
        if (!data) return;

        document.getElementById('repCount').textContent = data.rep_count || 0;
        document.getElementById('formQuality').textContent = `${Math.round(data.form_quality || 0)}%`;
        document.getElementById('currentState').textContent = data.current_state || 'STANDING';
        
        if (data.angles) {
            document.getElementById('torsoAngle').textContent = `${data.angles.torso}°`;
            document.getElementById('hipAngle').textContent = `${data.angles.hip}°`;
            document.getElementById('kneeAngle').textContent = `${data.angles.knee}°`;
        }
        
        this.updateFeedbackUI(data.feedback || []);
    }

    updateFeedbackUI(feedback) {
        const feedbackList = document.getElementById('feedbackList');
        feedbackList.innerHTML = '';
        
        if (feedback.length === 0) {
            feedbackList.innerHTML = '<div class="feedback-item">Waiting for analysis...</div>';
            return;
        }
        
        feedback.forEach(item => {
            const div = document.createElement('div');
            div.className = 'feedback-item';
            div.textContent = item;
            feedbackList.appendChild(div);
        });
    }

    updateHistoryUI(history) {
        const historyList = document.getElementById('repHistory');
        historyList.innerHTML = '';
        
        if (history.length === 0) {
            historyList.innerHTML = '<div class="history-item">No reps completed yet</div>';
            return;
        }
        
        // Show latest 5 reps
        const recentHistory = history.slice(-5).reverse();
        
        recentHistory.forEach(rep => {
            const div = document.createElement('div');
            div.className = 'history-item';
            div.innerHTML = `
                <span>Rep ${rep.rep_number}</span>
                <span>${rep.timestamp}</span>
                <span>${rep.form_quality}%</span>
            `;
            historyList.appendChild(div);
        });
    }
}

// Initialize the analyzer when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new DeadliftAnalyzer();
});

// Add some cool terminal-like effects
document.addEventListener('DOMContentLoaded', () => {
    const header = document.querySelector('.header h1');
    const text = header.textContent;
    header.textContent = '';
    
    let i = 0;
    const typeWriter = () => {
        if (i < text.length) {
            header.textContent += text.charAt(i);
            i++;
            setTimeout(typeWriter, 100);
        }
    };
    
    // Start typing effect after a short delay
    setTimeout(typeWriter, 1000);
});