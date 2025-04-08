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
active_streams = {}  # Store active stream objects
stream_lock = threading.Lock()  # Add thread lock for stream operations

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
    global active_streams
    
    rtsp_url = cameras[ip].get('rtsp_url')
    if not rtsp_url:
        return
    
    with stream_lock:
        # Check if there's already an active stream for this camera
        if ip in active_streams:
            try:
                active_streams[ip]['cap'].release()  # Release existing stream
            except:
                pass  # Ignore errors during release
            del active_streams[ip]
    
        cap = cv2.VideoCapture(rtsp_url)
        if not cap.isOpened():
            cameras[ip]['connected'] = False
            cameras[ip]['status'] = 'error'
            cameras[ip]['error_message'] = 'Failed to open stream'
            return
            
        active_streams[ip] = {
            'cap': cap,
            'active': True
        }
    
    try:
        while True:
            with stream_lock:
                if ip not in active_streams or not active_streams[ip]['active']:
                    break
                cap = active_streams[ip]['cap']
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Convert frame to JPEG
                ret, buffer = cv2.imencode('.jpg', frame)
                if not ret:
                    break
                frame = buffer.tobytes()
            
            # Return frame in multipart response
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    finally:
        with stream_lock:
            if ip in active_streams:
                try:
                    active_streams[ip]['cap'].release()
                except:
                    pass  # Ignore errors during release
                del active_streams[ip]
            cameras[ip]['connected'] = False
            cameras[ip]['status'] = 'discovered'

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
    
    # First stop any existing stream
    with stream_lock:
        if ip in active_streams:
            try:
                active_streams[ip]['active'] = False
                active_streams[ip]['cap'].release()
                del active_streams[ip]
            except:
                pass
    
    try:
        rtsp_url = get_rtsp_url(ip, username, password)
        if rtsp_url:
            cameras[ip]['rtsp_url'] = rtsp_url
            cameras[ip]['connected'] = True
            cameras[ip]['status'] = 'connected'
            cameras[ip]['username'] = username
            cameras[ip]['password'] = password
            cameras[ip].pop('error_message', None)  # Clear any error message
            return jsonify({"status": "success", "rtsp_url": rtsp_url})
        else:
            cameras[ip]['status'] = 'error'
            cameras[ip]['connected'] = False
            cameras[ip]['error_message'] = "Failed to get RTSP URL from camera"
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
    if ip not in cameras:
        return jsonify({
            "status": "error",
            "message": "Camera not found"
        }), 404
        
    if not cameras[ip].get('connected'):
        return jsonify({
            "status": "error",
            "message": "Camera not connected"
        }), 400
    
    try:
        return Response(
            get_camera_stream(ip),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
    except Exception as e:
        print(f"Stream error for {ip}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Stream error: {str(e)}"
        }), 500

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

@app.route('/api/stop_stream/<ip>', methods=['POST'])
def stop_stream(ip):
    """API endpoint to stop a camera stream"""
    try:
        with stream_lock:
            # Check if camera exists
            if ip not in cameras:
                return jsonify({
                    "status": "error",
                    "message": "Camera not found"
                }), 404

            # Stop the stream if active
            if ip in active_streams:
                try:
                    # Mark stream as inactive first
                    active_streams[ip]['active'] = False
                    # Then release the capture
                    active_streams[ip]['cap'].release()
                except Exception as e:
                    print(f"Error releasing stream for {ip}: {str(e)}")
                finally:
                    del active_streams[ip]

            # Update camera status regardless of whether stream was active
            cameras[ip]['connected'] = False
            cameras[ip]['status'] = 'discovered'
            cameras[ip].pop('error_message', None)  # Clear any error message
            
            return jsonify({
                "status": "success",
                "message": "Stream stopped successfully"
            })
    except Exception as e:
        print(f"Error stopping stream for {ip}: {str(e)}")
        # Attempt to clean up even if there was an error
        try:
            with stream_lock:
                if ip in active_streams:
                    active_streams[ip]['active'] = False
                    active_streams[ip]['cap'].release()
                    del active_streams[ip]
                if ip in cameras:
                    cameras[ip]['connected'] = False
                    cameras[ip]['status'] = 'discovered'
        except:
            pass
        
        return jsonify({
            "status": "error",
            "message": f"Failed to stop stream: {str(e)}"
        }), 500

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