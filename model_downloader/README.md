cat > README.md << 'EOF'
# ComfyUI Model Downloader

Download models directly from URLs to your ComfyUI installation or cloud storage.

## Features

- Download models to local ComfyUI checkpoints folder
- Upload models to cloud storage (60+ providers via rclone)
- Persistent credential storage (encrypted)
- Supports all rclone-compatible storage providers

## Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/yourusername/comfyui-model-downloader.git
cd comfyui-model-downloader
pip install -r requirements.txt
