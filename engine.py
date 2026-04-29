import cv2
import numpy as np
import sounddevice as sd
from datetime import datetime, timedelta
from collections import deque
import torch
from PIL import Image
import mediapipe as mp
import platform
from transformers import AutoImageProcessor, AutoModelForImageClassification
from ultralytics import YOLO
import threading
import uuid

torch.set_grad_enabled(False)

class SafetyEngine:
    def __init__(self):
        print("Initializing SafetyEngine...")
        # Load models
        from transformers import AutoImageProcessor, AutoModelForImageClassification
        self.processor = AutoImageProcessor.from_pretrained("dima806/fairface_gender_image_detection")
        self.gender_model = AutoModelForImageClassification.from_pretrained("dima806/fairface_gender_image_detection")
        self.weapon_model = YOLO("yolov8n.pt")
        self.WEAPON_CLASSES = ["knife", "scissors", "cell phone"] # adding cell phone as proxy for testing if needed
        
        # Mediapipe
        self.mp_face = mp.solutions.face_detection
        self.face_detector = self.mp_face.FaceDetection(model_selection=1, min_detection_confidence=0.7)
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(min_detection_confidence=0.6, min_tracking_confidence=0.6)
        
        # Audio setup
        self.fs = 16000
        self.SCREAM_THRESHOLD = 0.08
        self.scream_flag = False
        
        # Try starting audio stream
        try:
            self.audio_stream = sd.InputStream(callback=self.audio_callback, channels=1, samplerate=self.fs)
            self.audio_stream.start()
        except Exception as e:
            print("Could not initialize audio stream:", e)
            self.audio_stream = None

        # State
        self.male_count = 0
        self.female_count = 0
        self.people_count = 0
        self.risk_score = 0
        
        self.weapon_frames = 0
        self.sos_frames = 0
        self.scream_frames = 0
        self.fight_frames = 0
        
        self.PERSISTENCE_REQUIRED = 2
        self.RISK_WEIGHTS = {"weapon": 5, "sos": 4, "scream": 2, "fight": 3}
        self.RISK_THRESHOLD = 4
        
        self.recent_alerts = []
        self.last_alert_time = datetime.min
        self.ALERT_COOLDOWN = timedelta(seconds=10)
        
        # Camera
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) if platform.system() == "Windows" else cv2.VideoCapture(0)
        
        # Background subtractor for simple motion/fight detection
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=False)
        
        # Heatmap
        self.heatmap_accum = None
        self.decay_factor = 0.95
        
        self.frame_counter = 0
        self.last_results = []
        self.last_labels = {}
        
        self.lock = threading.Lock()
        
        # Add a startup alert to ensure UI is getting data
        self.add_alert('SYSTEM', 'System Online & Monitoring Active', 'info')

    def audio_callback(self, indata, frames, time, status):
        volume = np.sqrt(np.mean(indata**2))
        self.scream_flag = volume > self.SCREAM_THRESHOLD

    def classify_gender(self, face_bgr):
        face_rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(face_rgb)
        inputs = self.processor(images=img, return_tensors="pt")
        outputs = self.gender_model(**inputs)
        probs = torch.softmax(outputs.logits, dim=1)
        conf, pred = torch.max(probs, dim=1)
        label = self.gender_model.config.id2label[pred.item()]
        if conf.item() < 0.8:
            label = "Uncertain"
        return label

    def detect_sos(self, results):
        if not results.multi_hand_landmarks:
            return False
        for hand in results.multi_hand_landmarks:
            lm = hand.landmark
            tips = [8, 12, 16, 20]
            pips = [6, 10, 14, 18]
            folded = sum([1 for tip, pip in zip(tips, pips) if lm[tip].y > lm[pip].y])
            if folded >= 3:
                return True
        return False

    def add_alert(self, alert_type, message, level='high'):
        with self.lock:
            # prevent spamming same alert type
            if self.recent_alerts and self.recent_alerts[0]['type'] == alert_type and (datetime.now() - datetime.strptime(self.recent_alerts[0]['time'], '%H:%M:%S')).seconds < 5:
                return
            alert = {
                'id': str(uuid.uuid4()),
                'type': alert_type,
                'message': message,
                'time': datetime.now().strftime('%H:%M:%S'),
                'level': level
            }
            self.recent_alerts.insert(0, alert)
            if len(self.recent_alerts) > 50:
                self.recent_alerts.pop()

    def process_frame(self, use_heatmap=False):
        ret, frame = self.cap.read()
        if not ret:
            return None
        
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        if self.heatmap_accum is None:
            self.heatmap_accum = np.zeros((h, w), dtype=np.float32)
            
        # Decay heatmap
        self.heatmap_accum *= self.decay_factor
        
        # Local stats
        male = female = people = 0
        
        # Motion detection (for proxy fight detection)
        fg_mask = self.bg_subtractor.apply(frame)
        motion_ratio = cv2.countNonZero(fg_mask) / (h*w)
        if motion_ratio > 0.05:  # Significant motion proxy for "fight"
            self.fight_frames += 1
            self.heatmap_accum += fg_mask.astype(np.float32) * 0.1 # accumulate heatmap
        else:
            self.fight_frames = max(0, self.fight_frames - 1)

        self.frame_counter += 1

        faces = self.face_detector.process(rgb)
        if faces.detections:
            for i, det in enumerate(faces.detections):
                box = det.location_data.relative_bounding_box
                x = max(0, int(box.xmin * w))
                y = max(0, int(box.ymin * h))
                bw = int(box.width * w)
                bh = int(box.height * h)
                if bw < 40 or bh < 40:
                    continue
                face = frame[y:y+bh, x:x+bw]
                if face.size == 0:
                    continue
                    
                people += 1
                
                # Classify gender every 10 frames to save CPU, otherwise use last known or 'Person'
                label = "Person"
                if self.frame_counter % 10 == 0:
                    label = self.classify_gender(face)
                    # Simple cache mechanism based on approximate x,y could go here
                
                if label == "Male": male += 1
                elif label == "Female": female += 1
                
                # Update heatmap for people
                cv2.rectangle(self.heatmap_accum, (x,y), (x+bw, y+bh), 10, -1)
                
                cv2.rectangle(frame, (x,y), (x+bw,y+bh), (255,255,255), 2)
                cv2.putText(frame, label, (x,y-8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

        # Weapons (Run every 3 frames to save CPU)
        weapon_found = False
        if self.frame_counter % 3 == 0:
            self.last_results = self.weapon_model(frame, conf=0.35, verbose=False)
            
        for r in self.last_results:
            for box in r.boxes:
                cls = int(box.cls)
                label = self.weapon_model.names[cls]
                if label in self.WEAPON_CLASSES:
                    self.weapon_frames += 1
                    weapon_found = True
                    x1,y1,x2,y2 = map(int, box.xyxy[0])
                    cv2.rectangle(frame,(x1,y1),(x2,y2),(0,0,255),2)
                    cv2.putText(frame,label,(x1,y1-8),cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,0,255),2)
                    # Heatmap focus on weapons
                    cv2.rectangle(self.heatmap_accum, (x1,y1), (x2, y2), 50, -1)
        if not weapon_found:
            self.weapon_frames = 0
        # SOS
        hands_res = self.hands.process(rgb)
        if self.detect_sos(hands_res):
            self.sos_frames += 1
        else:
            self.sos_frames = 0

        # Scream
        if self.scream_flag:
            self.scream_frames += 1
        else:
            self.scream_frames = 0

        # Scoring
        score = 0
        if self.weapon_frames >= self.PERSISTENCE_REQUIRED:
            score += self.RISK_WEIGHTS["weapon"]
            self.add_alert('WEAPON', 'Weapon Detected', 'high')
        if self.sos_frames >= self.PERSISTENCE_REQUIRED:
            score += self.RISK_WEIGHTS["sos"]
            self.add_alert('SOS', 'SOS Gesture Detected', 'high')
        if self.scream_frames >= self.PERSISTENCE_REQUIRED:
            score += self.RISK_WEIGHTS["scream"]
            self.add_alert('SCREAM', 'Loud Scream Detected', 'high')
        if self.fight_frames >= self.PERSISTENCE_REQUIRED * 2:
            score += self.RISK_WEIGHTS["fight"]
            self.add_alert('FIGHT', 'Aggressive Motion/Fight Detected', 'warning')

        with self.lock:
            self.male_count = male
            self.female_count = female
            self.people_count = people
            self.risk_score = score
            
        if use_heatmap:
            # Apply colormap
            norm_heatmap = cv2.normalize(self.heatmap_accum, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            color_heatmap = cv2.applyColorMap(norm_heatmap, cv2.COLORMAP_JET)
            frame = cv2.addWeighted(frame, 0.6, color_heatmap, 0.4, 0)
            
        # Draw Overlays
        if score >= self.RISK_THRESHOLD:
            cv2.rectangle(frame, (0,0), (w,h), (0,0,255), 8)

        # Encode to JPG
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            return None
            
        return buffer.tobytes()

    def release(self):
        self.cap.release()
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
