from flask import Flask, Response, jsonify, send_from_directory, request
from flask_cors import CORS
from engine import SafetyEngine
import threading
import os

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)

# Initialize the ML Engine
print("Booting up Aegis AI System...")
engine = SafetyEngine()


def gen_frames(heatmap=False):
    while True:
        frame_bytes = engine.process_frame(use_heatmap=heatmap)
        if frame_bytes is None:
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    heatmap = request.args.get('heatmap', '0') == '1'
    return Response(gen_frames(heatmap=heatmap),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/stats')
def get_stats():
    with engine.lock:
        data = {
            "people": engine.people_count,
            "males": engine.male_count,
            "females": engine.female_count,
            "risk_score": engine.risk_score,
            "recent_alerts": engine.recent_alerts.copy()
        }
    return jsonify(data)

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, threaded=True)
    finally:
        engine.release()
