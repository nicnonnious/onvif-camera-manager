import os
import socket
import threading
from onvif import ONVIFCamera
import cv2
import time
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

def discover_cameras():
    """
    Discover cameras on the network using ONVIF WS-Discovery.
    Returns a list of discovered camera IPs.
    """
    discovered_cameras = []
    
    try:
        # Create a broadcast socket for ONVIF WS-Discovery
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(5)
        
        # WS-Discovery message
        discovery_msg = """<?xml version="1.0" encoding="UTF-8"?>
        <e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
            xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
            xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
            xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
            <e:Header>
                <w:MessageID>uuid:84ede3de-7dec-11d0-c360-f01234567890</w:MessageID>
                <w:To e:mustUnderstand="true">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
                <w:Action a:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
            </e:Header>
            <e:Body>
                <d:Probe>
                    <d:Types>dn:NetworkVideoTransmitter</d:Types>
                </d:Probe>
            </e:Body>
        </e:Envelope>"""
        
        # Send to broadcast address
        sock.sendto(discovery_msg.encode('utf-8'), ('255.255.255.255', 3702))
        
        # Listen for responses
        start_time = time.time()
        while time.time() - start_time < 5:  # Listen for 5 seconds
            try:
                data, addr = sock.recvfrom(65535)
                response = data.decode('utf-8')
                
                if 'NetworkVideoTransmitter' in response:
                    camera_ip = addr[0]
                    if camera_ip not in discovered_cameras:
                        discovered_cameras.append(camera_ip)
                        print(f"Found camera at {camera_ip}")
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error during discovery: {e}")
                continue
                
        sock.close()
        
    except Exception as e:
        print(f"Discovery error: {e}")
    
    return discovered_cameras

# Step 2: Retrieve RTSP URL from Camera
def get_rtsp_url(camera_ip, username, password):
    """
    Retrieve the RTSP URL from an ONVIF-compatible camera.
    """
    try:
        # Initialize the ONVIF camera object
        mycam = ONVIFCamera(camera_ip, 80, username, password)
        
        # Get the media service
        media_service = mycam.create_media_service()
        profiles = media_service.GetProfiles()
        token = profiles[0].token
        
        # Get the RTSP stream URI
        stream_uri = media_service.GetStreamUri({
            'StreamSetup': {'Stream': 'RTP-Unicast', 'Transport': 'RTSP'},
            'ProfileToken': token
        })
        
        rtsp_url = stream_uri.Uri
        return rtsp_url.replace("rtsp://", f"rtsp://{username}:{password}@")
    except Exception as e:
        print(f"Failed to retrieve RTSP URL for {camera_ip}: {e}")
        return None

# Step 3: Verify and Display Stream
def verify_stream(rtsp_url):
    """
    Verify the RTSP stream by opening it with OpenCV.
    """
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        print(f"Failed to open stream: {rtsp_url}")
        return False

    print(f"Stream opened successfully: {rtsp_url}")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Stream ended.")
            break
        cv2.imshow("Camera Stream", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    return True

# Main Function
def main(username, password):
    print("Discovering cameras on the network...")
    cameras = discover_cameras()
    
    if not cameras:
        print("No cameras found on the network.")
        return

    print(f"Found {len(cameras)} camera(s): {cameras}")

    for camera_ip in cameras:
        print(f"Retrieving RTSP URL for camera at {camera_ip}...")
        rtsp_url = get_rtsp_url(camera_ip, username, password)
        
        if rtsp_url:
            print(f"RTSP URL for {camera_ip}: {rtsp_url}")
            print("Verifying stream...")
            verify_stream(rtsp_url)
        else:
            print(f"Could not retrieve RTSP URL for camera at {camera_ip}.")


if __name__ == "__main__":
    print("Please use the web interface to discover and manage cameras.")
    print("Run 'python web_app.py' to start the web interface.")