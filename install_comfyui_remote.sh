#!/bin/bash
# ============================================================
# ComfyUI Install Script for Remote PC (192.168.1.200)
# Run this on the OTHER laptop
# ============================================================

set -e

INSTALL_DIR="$HOME/ComfyUI"
PORT=8188

echo "=========================================="
echo "  ComfyUI Remote Install Script"
echo "  Target: 0.0.0.0:$PORT (all interfaces)"
echo "=========================================="

# --- 1. System dependencies ---
echo ""
echo "[1/6] Installing system dependencies..."
if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3 python3-pip python3-venv git git-lfs
elif command -v dnf &>/dev/null; then
    sudo dnf install -y python3 python3-pip git git-lfs
elif command -v pacman &>/dev/null; then
    sudo pacman -S --noconfirm python python-pip git git-lfs
else
    echo "WARNING: Unknown package manager. Install python3, pip, git manually."
fi

# --- 2. Check GPU ---
echo ""
echo "[2/6] Detecting GPU..."
if command -v nvidia-smi &>/dev/null; then
    echo "NVIDIA GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    HAS_NVIDIA=true
elif lspci 2>/dev/null | grep -qi amd; then
    echo "AMD GPU detected (ROCm support may be needed)"
    HAS_NVIDIA=false
else
    echo "No dedicated GPU detected. Will run on CPU (slow)."
    HAS_NVIDIA=false
fi

# --- 3. Clone ComfyUI ---
echo ""
echo "[3/6] Cloning ComfyUI..."
if [ -d "$INSTALL_DIR" ]; then
    echo "ComfyUI directory already exists at $INSTALL_DIR"
    echo "Pulling latest changes..."
    cd "$INSTALL_DIR" && git pull
else
    git clone https://github.com/comfyanonymous/ComfyUI.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# --- 4. Create venv and install deps ---
echo ""
echo "[4/6] Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

echo "Installing PyTorch..."
if [ "$HAS_NVIDIA" = true ]; then
    pip install --upgrade pip -q
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 -q
else
    pip install --upgrade pip -q
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu -q
fi

echo "Installing ComfyUI requirements..."
pip install -r requirements.txt -q

# --- 5. Install ComfyUI Manager ---
echo ""
echo "[5/6] Installing ComfyUI Manager..."
if [ ! -d "custom_nodes/ComfyUI-Manager" ]; then
    cd custom_nodes
    git clone https://github.com/Comfy-Org/ComfyUI-Manager.git
    cd ..
fi

# --- 6. Create startup script ---
echo ""
echo "[6/6] Creating startup script..."
cat > "$INSTALL_DIR/start.sh" << 'STARTEOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate

echo "Starting ComfyUI on 0.0.0.0:8188..."
echo "Access from network: http://$(hostname -I | awk '{print $1}'):8188"
echo ""

# Detect GPU and set flags
if command -v nvidia-smi &>/dev/null; then
    python main.py --listen 0.0.0.0 --port 8188 "$@"
else
    python main.py --listen 0.0.0.0 --port 8188 --cpu "$@"
fi
STARTEOF
chmod +x "$INSTALL_DIR/start.sh"

# Create systemd service (optional, for auto-start)
cat > /tmp/comfyui.service << SERVICEEOF
[Unit]
Description=ComfyUI Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python main.py --listen 0.0.0.0 --port 8188
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
SERVICEEOF

echo ""
echo "=========================================="
echo "  Installation Complete!"
echo "=========================================="
echo ""
echo "To start ComfyUI:"
echo "  cd $INSTALL_DIR && ./start.sh"
echo ""
echo "Or install as a service (auto-start on boot):"
echo "  cp /tmp/comfyui.service ~/.config/systemd/user/"
echo "  systemctl --user daemon-reload"
echo "  systemctl --user enable comfyui"
echo "  systemctl --user start comfyui"
echo ""
echo "Access ComfyUI at:"
MY_IP=$(hostname -I | awk '{print $1}')
echo "  Local:   http://localhost:8188"
echo "  Network: http://$MY_IP:8188"
echo ""
echo "From Lumina Video Studio PC, it will connect to:"
echo "  http://192.168.1.200:8188"
echo ""
echo "IMPORTANT: After ComfyUI starts, load and run a test"
echo "workflow first before using it in Lumina Video Studio."
echo ""
