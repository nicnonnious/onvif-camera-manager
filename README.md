# ONVIF Camera Manager

A web-based application for discovering, managing, and viewing ONVIF-compatible IP cameras on your network. This application provides an intuitive interface for camera discovery, live streaming, and VMS integration.

## Features

- **Automatic Camera Discovery**: Utilizes ONVIF WS-Discovery to automatically find cameras on your network
- **Web-Based Interface**: Modern, responsive UI for managing your cameras
- **Live Streaming**: View live streams from your cameras directly in the browser
- **Credential Management**: Secure handling of camera credentials
- **VMS Integration**: Generate registration codes for easy camera integration with Video Management Systems
- **Multi-Camera Support**: Manage multiple cameras simultaneously
- **Real-time Status**: Monitor camera connection status and health

## Prerequisites

- Python 3.7 or higher
- Network access to your IP cameras
- ONVIF-compatible IP cameras
- Cameras must be on the same network as the server

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd onvif-camera-manager
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
```

3. Activate the virtual environment:
- Windows:
```bash
venv\Scripts\activate
```
- Linux/Mac:
```bash
source venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the application:
```bash
python web_app.py
```

2. Open your web browser and navigate to:
```
http://localhost:5000
```

3. On first access:
   - You'll be prompted to enter default credentials for your cameras
   - These credentials will be used for initial camera discovery
   - You can override credentials for individual cameras later

4. Main features:
   - **Discover Cameras**: Click the "Discover Cameras" button to scan your network
   - **Connect to Cameras**: Click "Connect" on any discovered camera to establish a connection
   - **View Streams**: Connected cameras will display their live stream
   - **Generate Registration Codes**: Get registration codes for VMS integration
   - **Manage Credentials**: Update credentials per camera as needed

## Camera Status Indicators

- **Blue**: Camera discovered but not connected
- **Green**: Camera connected and streaming
- **Red**: Camera offline or unreachable
- **Yellow**: Connection error or authentication failure

## Security Features

- No hardcoded credentials
- Credentials stored only in memory during runtime
- Secure credential handling per camera
- Session-based authentication
- Automatic session cleanup on logout

## VMS Integration

1. Connect to a camera using valid credentials
2. Click "Get Registration Code"
3. Copy either:
   - The RTSP URL for direct stream access
   - The registration code for automated VMS setup

## Troubleshooting

1. **Camera Not Found**:
   - Ensure the camera is powered on and connected to the network
   - Verify the camera is ONVIF-compatible
   - Check network firewall settings

2. **Connection Failed**:
   - Verify camera credentials
   - Ensure camera is not locked due to failed attempts
   - Check camera's ONVIF service status

3. **Stream Not Loading**:
   - Verify browser supports RTSP streaming
   - Check network bandwidth and firewall settings
   - Ensure camera stream settings are compatible

## Technical Details

- Built with Flask web framework
- Uses ONVIF protocol for camera communication
- Implements WS-Discovery for camera detection
- Supports RTSP streaming
- Real-time status updates
- Responsive Bootstrap-based UI

## Dependencies

Core dependencies:
- Flask 3.1.0
- onvif-zeep 0.2.12
- opencv-python 4.11.0.86

For a complete list of dependencies, see `requirements.txt`

## Network Requirements

- ONVIF port (typically 80) must be accessible
- WS-Discovery port (3702) must be accessible for discovery
- RTSP ports (typically 554) must be accessible for streaming
- Network must allow UDP broadcast for discovery

## Contributing

Contributions are welcome! Please feel free to submit pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built using the ONVIF ZEEP library
- Uses Bootstrap for UI components
- OpenCV for video stream handling 