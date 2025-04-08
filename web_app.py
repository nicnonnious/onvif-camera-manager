from flask import Flask, render_template, jsonify, request, Response, session, redirect, url_for
import json
from app import discover_cameras, get_rtsp_url, ONVIFCamera
import cv2
import threading
import time
from datetime import datetime
import base64
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Generate a random secret key for sessions

# Global variables to store camera information and credentials
cameras = {}
last_discovery_time = None
default_credentials = None

def discover_and_update_cameras():
    """Discover cameras and update the global cameras dictionary"""
    global cameras, last_discovery_time, default_credentials
    
    if not default_credentials:
        return []
        
    discovered = discover_cameras()
    
    # Update camera information
    for ip in discovered:
        if ip not in cameras:
            cameras[ip] = {
                'ip': ip,
                'status': 'discovered',
                'rtsp_url': None,
                'last_seen': datetime.now().isoformat(),
                'connected': False,
                'username': default_credentials['username'],
                'password': default_credentials['password']
            }
    
    # Mark cameras that are no longer visible
    current_ips = set(discovered)
    for ip in list(cameras.keys()):
        if ip not in current_ips:
            cameras[ip]['status'] = 'offline'
            cameras[ip]['connected'] = False
    
    last_discovery_time = datetime.now().isoformat()
    return discovered

def get_camera_stream(ip):
    """Generator function to stream camera feed"""
    rtsp_url = cameras[ip].get('rtsp_url')
    if not rtsp_url:
        return
    
    cap = cv2.VideoCapture(rtsp_url)
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Convert frame to JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        
        # Return frame in multipart response
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    
    cap.release()

@app.route('/')
def index():
    """Render the main page or redirect to login"""
    if not default_credentials:
        return redirect(url_for('login'))
    return render_template('index.html', cameras=cameras)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle login page"""
    global default_credentials
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username and password:
            default_credentials = {
                'username': username,
                'password': password
            }
            # Do initial camera discovery with new credentials
            discover_and_update_cameras()
            return redirect(url_for('index'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Clear credentials and redirect to login"""
    global default_credentials, cameras
    default_credentials = None
    cameras = {}
    return redirect(url_for('login'))

@app.route('/api/discover', methods=['POST'])
def api_discover():
    """API endpoint to trigger camera discovery"""
    if not default_credentials:
        return jsonify({"status": "error", "message": "No credentials provided"})
    
    discover_and_update_cameras()
    return jsonify({"status": "success", "cameras": cameras})

@app.route('/api/connect', methods=['POST'])
def api_connect():
    """API endpoint to connect to a camera"""
    if not default_credentials:
        return jsonify({"status": "error", "message": "No credentials provided"})
    
    data = request.json
    ip = data.get('ip')
    username = data.get('username', default_credentials['username'])
    password = data.get('password', default_credentials['password'])
    
    if ip not in cameras:
        return jsonify({"status": "error", "message": "Camera not found"})
    
    try:
        rtsp_url = get_rtsp_url(ip, username, password)
        if rtsp_url:
            cameras[ip]['rtsp_url'] = rtsp_url
            cameras[ip]['connected'] = True
            cameras[ip]['status'] = 'connected'
            cameras[ip]['username'] = username
            cameras[ip]['password'] = password
            return jsonify({"status": "success", "rtsp_url": rtsp_url})
        else:
            return jsonify({"status": "error", "message": "Failed to get RTSP URL from camera"})
    except Exception as e:
        cameras[ip]['status'] = 'error'
        cameras[ip]['connected'] = False
        cameras[ip]['error_message'] = str(e)
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route('/api/stream/<ip>')
def api_stream(ip):
    """API endpoint to stream camera feed"""
    if ip not in cameras or not cameras[ip].get('connected'):
        return "Camera not connected", 400
    
    return Response(
        get_camera_stream(ip),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/api/cameras')
def api_cameras():
    """API endpoint to get camera information"""
    return jsonify(cameras)

@app.route('/api/registration_code', methods=['POST'])
def api_registration_code():
    """Generate a registration code for VMS integration"""
    data = request.json
    ip = data.get('ip')
    username = data.get('username', 'admin')
    password = data.get('password', '1234abcd')
    
    if ip not in cameras:
        return jsonify({"status": "error", "message": "Camera not found"})
    
    try:
        # Get RTSP URL if not already connected
        rtsp_url = cameras[ip].get('rtsp_url')
        if not rtsp_url:
            rtsp_url = get_rtsp_url(ip, username, password)
            if rtsp_url:
                cameras[ip]['rtsp_url'] = rtsp_url
                cameras[ip]['connected'] = True
                cameras[ip]['status'] = 'connected'
        
        if rtsp_url:
            # Create registration code with camera details
            registration_data = {
                "ip": ip,
                "username": username,
                "password": password,
                "rtsp_url": rtsp_url,
                "timestamp": datetime.now().isoformat()
            }
            
            # Encode the data as base64 for easy copying
            registration_code = base64.b64encode(
                json.dumps(registration_data).encode()
            ).decode()
            
            return jsonify({
                "status": "success",
                "registration_code": registration_code,
                "camera_name": f"ONVIF Camera {ip}",
                "rtsp_url": rtsp_url
            })
        else:
            return jsonify({"status": "error", "message": "Failed to get RTSP URL from camera"})
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

if __name__ == '__main__':
    # Start discovery thread
    def discovery_thread():
        while True:
            if default_credentials:  # Only run discovery if we have credentials
                discover_and_update_cameras()
            time.sleep(30)
    
    threading.Thread(target=discovery_thread, daemon=True).start()
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False) 