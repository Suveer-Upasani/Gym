import cv2
import mediapipe as mp
import numpy as np
import time
import math
import csv
import os
from flask import Flask, render_template, Response, request, jsonify
from collections import deque
import base64
import threading
from datetime import datetime

app = Flask(__name__)

# -------------------- Initialize MediaPipe --------------------
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5, model_complexity=1)

# Global variables for storing analysis data
current_frame = None
analysis_data = {
    'rep_count': 0,
    'form_quality': 0,
    'current_state': 'STANDING',
    'angles': {'torso': 0, 'hip': 0, 'knee': 0},
    'feedback': []
}
rep_history = []
frame_lock = threading.Lock()

# -------------------- Enhanced Helper Functions --------------------
def lm_to_pixel(landmark, width, height):
    return int(landmark.x * width), int(landmark.y * height)

def angle_with_vertical(vx, vy):
    dot = vx * 0 + vy * (-1)
    mag_v = math.hypot(vx, vy)
    if mag_v == 0:
        return 0.0
    cos_a = max(min(dot / mag_v, 1), -1)
    return math.degrees(math.acos(cos_a))

def angle_between_points(a, b, c):
    ba = np.array([a[0]-b[0], a[1]-b[1]])
    bc = np.array([c[0]-b[0], c[1]-b[1]])
    cos_angle = np.dot(ba, bc) / (np.linalg.norm(ba)*np.linalg.norm(bc)+1e-6)
    cos_angle = max(min(cos_angle,1),-1)
    return math.degrees(np.arccos(cos_angle))

def calculate_deadlift_reference_points(ankle_px, knee_px, shoulder_px, hip_px, frame_height):
    mid_foot_x = ankle_px[0]
    knee_height = knee_px[1]
    shoulder_height = shoulder_px[1]
    optimal_hip_height = knee_height + (shoulder_height - knee_height) * 0.6
    
    return {
        'vertical_line_x': mid_foot_x,
        'optimal_hip_height': optimal_hip_height,
        'mid_foot': (mid_foot_x, ankle_px[1])
    }

def draw_plus_sign_reference(img, reference_points, size=150, color=(0, 255, 255), thickness=3):
    vx = reference_points['vertical_line_x']
    hip_y = int(reference_points['optimal_hip_height'])
    mid_foot = reference_points['mid_foot']
    
    # Vertical reference line
    cv2.line(img, (vx, 0), (vx, img.shape[0]), color, thickness-1)
    
    # Horizontal reference line
    cv2.line(img, (vx-size, hip_y), (vx+size, hip_y), color, thickness-1)
    
    # Plus sign center
    center_x, center_y = vx, hip_y
    arm_length = size // 2
    
    # Enhanced plus sign
    cv2.line(img, (center_x, center_y - arm_length), (center_x, center_y + arm_length), 
             (255, 255, 255), thickness+1)
    cv2.line(img, (center_x - arm_length, center_y), (center_x + arm_length, center_y), 
             (255, 255, 255), thickness+1)
    cv2.circle(img, (center_x, center_y), arm_length, color, thickness)
    cv2.circle(img, (center_x, center_y), 15, (0, 0, 255), -1)
    
    # Labels
    cv2.putText(img, "IDEAL HIP HEIGHT", (center_x + 40, center_y - 10), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    cv2.putText(img, "BAR PATH", (center_x + 10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    
    # Mid-foot marker
    cv2.circle(img, mid_foot, 8, (0, 255, 0), -1)
    cv2.putText(img, "MID-FOOT", (mid_foot[0] - 40, mid_foot[1] + 25), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

def calculate_form_quality(hip_px, knee_px, shoulder_px, ankle_px, reference_points):
    vx = reference_points['vertical_line_x']
    optimal_hip_y = reference_points['optimal_hip_height']
    
    # Hip alignment quality
    hip_v_alignment = 100 - min(100, (abs(hip_px[0] - vx) / (vx * 0.2 + 1e-6)) * 100)
    
    # Hip height quality
    hip_h_alignment = 100 - min(100, (abs(hip_px[1] - optimal_hip_y) / (optimal_hip_y * 0.3 + 1e-6)) * 100)
    
    # Back angle quality
    back_angle = angle_with_vertical(shoulder_px[0]-hip_px[0], shoulder_px[1]-hip_px[1])
    back_quality = 100 - min(100, abs(back_angle - 50) / 50 * 100)
    
    # Hip-knee-ankle alignment
    hip_knee_dist = math.hypot(hip_px[0]-knee_px[0], hip_px[1]-knee_px[1])
    knee_ankle_dist = math.hypot(knee_px[0]-ankle_px[0], knee_px[1]-ankle_px[1])
    alignment_ratio = hip_knee_dist / (knee_ankle_dist + 1e-6)
    alignment_quality = 100 - min(100, abs(alignment_ratio - 1.2) / 1.2 * 100)
    
    overall_quality = (hip_v_alignment + hip_h_alignment + back_quality + alignment_quality) / 4
    
    return {
        'overall': overall_quality,
        'hip_vertical': hip_v_alignment,
        'hip_height': hip_h_alignment,
        'back_angle': back_quality,
        'hip_knee_alignment': alignment_quality
    }

def draw_form_feedback(img, hip_px, form_quality, reference_points):
    vx = reference_points['vertical_line_x']
    optimal_y = int(reference_points['optimal_hip_height'])
    
    # Draw current hip position
    cv2.circle(img, hip_px, 12, (0, 0, 255), -1)
    cv2.circle(img, hip_px, 12, (255, 255, 255), 2)
    
    # Connection lines to reference
    cv2.line(img, hip_px, (vx, hip_px[1]), (255, 100, 100), 2)
    cv2.line(img, hip_px, (hip_px[0], optimal_y), (255, 100, 100), 2)
    
    # Quality indicator
    if form_quality['overall'] > 80:
        quality_color = (0, 255, 0)
    elif form_quality['overall'] > 60:
        quality_color = (0, 255, 255)
    else:
        quality_color = (0, 0, 255)
    
    # Quality bar
    bar_x, bar_y = 20, img.shape[0] - 100
    bar_width = 200
    bar_height = 20
    cv2.rectangle(img, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), (50, 50, 50), -1)
    cv2.rectangle(img, (bar_x, bar_y), (bar_x + int(bar_width * form_quality['overall'] / 100), bar_y + bar_height), quality_color, -1)
    cv2.putText(img, f"FORM: {form_quality['overall']:.0f}%", (bar_x, bar_y - 10), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, quality_color, 2)

class DeadliftRepDetector:
    def __init__(self):
        self.state = "STANDING"
        self.rep_count = 0
        self.standing_threshold = 160
        self.bottom_threshold = 80
        self.hip_height_threshold = 0.005
        self.last_hip_y = None
        
    def update(self, hip_y_norm, torso_angle, hip_angle, knee_angle, form_quality):
        rep_completed = False
        
        if self.last_hip_y is None:
            self.last_hip_y = hip_y_norm
            return rep_completed, self.state
        
        hip_moving_down = hip_y_norm > self.last_hip_y + self.hip_height_threshold
        hip_moving_up = hip_y_norm < self.last_hip_y - self.hip_height_threshold
        
        if self.state == "STANDING":
            if torso_angle < self.standing_threshold - 10 and hip_moving_down:
                self.state = "DESCENDING"
                
        elif self.state == "DESCENDING":
            if torso_angle < self.bottom_threshold and hip_angle < 110:
                self.state = "BOTTOM"
                
        elif self.state == "BOTTOM":
            if hip_moving_up and torso_angle > self.bottom_threshold + 5:
                self.state = "ASCENDING"
                
        elif self.state == "ASCENDING":
            if torso_angle > self.standing_threshold - 5 and hip_angle > 165:
                self.state = "STANDING"
                self.rep_count += 1
                rep_completed = True
        
        self.last_hip_y = hip_y_norm
        return rep_completed, self.state

rep_detector = DeadliftRepDetector()

def process_frame(frame_data):
    global current_frame, analysis_data, rep_detector
    
    try:
        # Decode base64 image
        img_data = base64.b64decode(frame_data.split(',')[1])
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return
        
        h, w = frame.shape[:2]
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Create analysis frame (black background)
        analysis_frame = np.zeros((h, w, 3), dtype=np.uint8)
        
        pose_results = pose.process(rgb_frame)
        
        if pose_results.pose_landmarks:
            lm = pose_results.pose_landmarks.landmark
            
            # Determine side visibility
            left_hip_vis = lm[mp_pose.PoseLandmark.LEFT_HIP].visibility
            right_hip_vis = lm[mp_pose.PoseLandmark.RIGHT_HIP].visibility
            use_left = left_hip_vis >= right_hip_vis and left_hip_vis > 0.5
            use_right = right_hip_vis > left_hip_vis and right_hip_vis > 0.5
            
            if use_left or use_right:
                side_name = "LEFT" if use_left else "RIGHT"
                
                if use_left:
                    hip_idx, knee_idx, ankle_idx, shoulder_idx = (
                        mp_pose.PoseLandmark.LEFT_HIP, mp_pose.PoseLandmark.LEFT_KNEE,
                        mp_pose.PoseLandmark.LEFT_ANKLE, mp_pose.PoseLandmark.LEFT_SHOULDER
                    )
                else:
                    hip_idx, knee_idx, ankle_idx, shoulder_idx = (
                        mp_pose.PoseLandmark.RIGHT_HIP, mp_pose.PoseLandmark.RIGHT_KNEE,
                        mp_pose.PoseLandmark.RIGHT_ANKLE, mp_pose.PoseLandmark.RIGHT_SHOULDER
                    )

                # Get pixel coordinates
                hip_px = lm_to_pixel(lm[hip_idx], w, h)
                knee_px = lm_to_pixel(lm[knee_idx], w, h)
                ankle_px = lm_to_pixel(lm[ankle_idx], w, h)
                shoulder_px = lm_to_pixel(lm[shoulder_idx], w, h)

                # Calculate reference points and form quality
                reference_points = calculate_deadlift_reference_points(
                    ankle_px, knee_px, shoulder_px, hip_px, h
                )
                form_quality = calculate_form_quality(
                    hip_px, knee_px, shoulder_px, ankle_px, reference_points
                )

                # Calculate angles
                torso_angle = angle_with_vertical(shoulder_px[0]-hip_px[0], shoulder_px[1]-hip_px[1])
                hip_angle = angle_between_points(shoulder_px, hip_px, knee_px)
                knee_angle = angle_between_points(hip_px, knee_px, ankle_px)

                # Update rep detection
                rep_completed, current_state = rep_detector.update(
                    lm[hip_idx].y, torso_angle, hip_angle, knee_angle, form_quality
                )

                # Draw on both frames
                for canvas in [frame, analysis_frame]:
                    # Draw skeleton
                    mp_drawing.draw_landmarks(
                        canvas, pose_results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                        landmark_drawing_spec=mp_drawing.DrawingSpec(color=(0,255,0), thickness=2, circle_radius=4),
                        connection_drawing_spec=mp_drawing.DrawingSpec(color=(0,200,255), thickness=3)
                    )
                    
                    # Draw reference system
                    draw_plus_sign_reference(canvas, reference_points, size=200)
                    draw_form_feedback(canvas, hip_px, form_quality, reference_points)
                    
                    # Display info
                    cv2.putText(canvas, f"Reps: {rep_detector.rep_count} | State: {rep_detector.state}", 
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.putText(canvas, f"Form: {form_quality['overall']:.0f}%", 
                                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    cv2.putText(canvas, f"Torso: {torso_angle:.1f}° Hip: {hip_angle:.1f}° Knee: {knee_angle:.1f}°", 
                                (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                # Update analysis data
                analysis_data.update({
                    'rep_count': rep_detector.rep_count,
                    'form_quality': form_quality['overall'],
                    'current_state': rep_detector.state,
                    'angles': {
                        'torso': round(torso_angle, 1),
                        'hip': round(hip_angle, 1),
                        'knee': round(knee_angle, 1)
                    },
                    'feedback': [
                        f"Hip Alignment: {form_quality['hip_vertical']:.0f}%",
                        f"Hip Height: {form_quality['hip_height']:.0f}%",
                        f"Back Angle: {form_quality['back_angle']:.0f}%"
                    ]
                })
                
                if rep_completed:
                    rep_history.append({
                        'rep_number': rep_detector.rep_count,
                        'timestamp': datetime.now().strftime("%H:%M:%S"),
                        'form_quality': round(form_quality['overall'], 1)
                    })
        
        # Combine frames side by side
        combined = np.hstack((frame, analysis_frame))
        
        # Encode combined frame
        _, buffer = cv2.imencode('.jpg', combined, [cv2.IMWRITE_JPEG_QUALITY, 80])
        frame_bytes = buffer.tobytes()
        
        with frame_lock:
            current_frame = frame_bytes
            
    except Exception as e:
        print(f"Error processing frame: {e}")

# -------------------- Flask Routes --------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_frame', methods=['POST'])
def upload_frame():
    try:
        data = request.get_json()
        if data and 'frame' in data:
            # Process frame in background thread
            threading.Thread(target=process_frame, args=(data['frame'],)).start()
            return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error in upload_frame: {e}")
    return jsonify({'status': 'error'})

@app.route('/video_feed')
def video_feed():
    def generate():
        while True:
            with frame_lock:
                if current_frame is not None:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + current_frame + b'\r\n')
                else:
                    # Send a black frame if no data
                    black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    _, buffer = cv2.imencode('.jpg', black_frame)
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.03)  # ~30 FPS
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/analysis_data')
def get_analysis_data():
    return jsonify(analysis_data)

@app.route('/rep_history')
def get_rep_history():
    return jsonify(rep_history)

@app.route('/reset_session', methods=['POST'])
def reset_session():
    global rep_detector, analysis_data, rep_history
    rep_detector = DeadliftRepDetector()
    analysis_data = {
        'rep_count': 0,
        'form_quality': 0,
        'current_state': 'STANDING',
        'angles': {'torso': 0, 'hip': 0, 'knee': 0},
        'feedback': []
    }
    rep_history = []
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5005))
    
    # Run the app
    app.run(host='0.0.0.0', port=port, debug=False)
