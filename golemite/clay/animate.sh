#!/bin/bash
# Golemite Animation Script - Entry point for the clay

set -e

echo "🪨 Golemite Clay v1.0"
echo "====================="

# Set defaults
FORMATION="${FORMATION:-base}"
HOST="0.0.0.0"
VNC_PORT=5900
NOVNC_PORT=8080
API_PORT=5000

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --formation)
            FORMATION="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "Formation: $FORMATION"
echo "Host: $HOST"
echo "Ports: VNC:$VNC_PORT, noVNC:$NOVNC_PORT, API:$API_PORT"

# Start X virtual framebuffer
echo "Starting Xvfb..."
Xvfb :99 -screen 0 1280x1024x24 &
XVFB_PID=$!

# Set display
export DISPLAY=:99

# Start window manager
echo "Starting window manager..."
fluxbox &
FLUXBOX_PID=$!

# Start VNC server
echo "Starting VNC server..."
x11vnc -display :99 -forever -shared -rfbport ${VNC_PORT} -bg -nopw
VNC_PID=$!

# Start noVNC web interface
echo "Starting noVNC web interface..."
websockify --web /usr/share/novnc ${NOVNC_PORT} ${HOST}:${VNC_PORT} &
NOVNC_PID=$!

# Start the mission API server
echo "Starting mission control API..."
python3 /golemite/mission_api.py --port ${API_PORT} --formation ${FORMATION} &
API_PID=$!

# Wait for all services to start
sleep 2

echo "✅ Golemite is fully animated and awaiting commands"
echo "   Web interface: http://${HOST}:${NOVNC_PORT}/vnc.html"
echo "   API endpoint: http://${HOST}:${API_PORT}/api"

# Keep container running
wait $XVFB_PID
