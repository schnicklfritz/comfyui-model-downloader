# ComfyUI Cloud Model Downloader

Download models directly to your cloud GPU instance without wasting local bandwidth.

## The Problem

**You're on a slow home connection. You want to use a model on your rented GPU.**

Traditional workflow:
1. Download model to your PC (2 hours on slow connection)
2. Upload to cloud storage or GPU pod (3 hours)
3. Manually sort into correct ComfyUI folder
4. **Total: 5+ hours wasted**

**This tool fixes that.**

## What It Does

1. Capture authenticated download URLs from any site (TensorArt, CivitAI, HuggingFace, etc.)
2. Send URL directly to your cloud GPU
3. Downloads at datacenter speeds (minutes, not hours)
4. Auto-detects model type (checkpoint/LoRA/VAE/etc.)
5. Places in correct ComfyUI folder automatically
6. Optional: Upload directly to cloud storage via rclone

**Works with any model hosting site that gives you download access.**

---

## Installation

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/schnicklfritz/comfyui-model-downloader.git
cd comfyui-model-downloader
pip install -r requirements.txt

