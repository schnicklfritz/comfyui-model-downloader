# ComfyUI Cloud Model Downloader

Download models directly from cloud URLs (HuggingFace, TensorArt, CivitAI, etc.) into ComfyUI with automatic model type detection.

## Features

- **Direct URL downloads** - Paste any direct download link
- **Smart auto-detection** - Analyzes safetensors metadata and tensor names to determine model type
- **Confidence scoring** - Uncertain files go to `models/unknown/` for manual review
- **Progress tracking** - Real-time download progress bar
- **Multiple sources** - Works with HuggingFace, TensorArt, CivitAI, private links, etc.
- **All model types** - Checkpoints, LoRAs, VAEs, ControlNet, Upscalers, Embeddings, CLIP

## Installation

### 1. Clone to custom_nodes

```bash
cd /workspace/ComfyUI/custom_nodes/
git clone https://github.com/yourusername/comfyui-model-downloader.git
```

Or manually download and extract to:
```
ComfyUI/custom_nodes/comfyui-model-downloader/
```

### 2. Install dependencies

```bash
cd comfyui-model-downloader
pip install -r requirements.txt
```

### 3. Restart ComfyUI

The node will appear in the `model_management` category.

## Usage

### In ComfyUI Workflow

1. Add node: **Cloud Model Downloader**
2. **URL**: Paste direct download link
3. **Model Type**: 
   - `auto` - Automatic detection (recommended)
   - Or manually select: checkpoints, loras, vae, controlnet, etc.
4. **Filename**: Optional - Override the filename
5. Run workflow - Model downloads to appropriate folder

### Getting Direct URLs

#### HuggingFace
- Right-click download button → Copy Link Address
- Format: `https://huggingface.co/user/repo/resolve/main/model.safetensors`

#### TensorArt
- Press `Ctrl+J` (Chrome) or `Ctrl+Shift+J` (Firefox) while downloading
- Copy the download URL from browser's download manager

#### CivitAI
- Click download button
- Copy the direct link from your browser's download manager

## Model Type Detection

### Detection Priority

1. **Safetensors Metadata** (90% confidence)
   - Reads tensor names from file header
   - Checks for specific patterns:
     - VAE: `encoder.*`, `decoder.*`, `quant_conv`
     - LoRA: `lora_unet.*`, `lora_te.*`, `.lora_up.`, `.lora_down.`
     - Checkpoint: `model.diffusion_model.*`, `cond_stage_model`
     - ControlNet: `control_model.*`
     - CLIP: `text_model.*`, `embeddings.*`

2. **Filename Patterns** (80% confidence)
   - Keywords: `vae`, `lora`, `controlnet`, `upscale`, `clip`, etc.

3. **File Size** (30-60% confidence)
   - Last resort only
   - Large files (>3GB) → likely checkpoints
   - Medium/small → unclear, goes to `unknown/`

### Uncertain Detection

Files with <70% confidence go to `models/unknown/` with explanation:

```
⚠ Low confidence detection (40%)
  Reason: medium file (450MB) - could be LoRA or VAE
  → Placing in models/unknown/ for manual review
```

You can then manually move the file to the correct folder.

## File Structure

```
comfyui-model-downloader/
├── __init__.py                    # ComfyUI node registration
├── cloud_model_downloader.py      # Main node implementation
├── bookmarklet.js                 # Browser bookmarklet (optional)
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## Output Folders

Models are saved to ComfyUI's standard directories:

- `ComfyUI/models/checkpoints/` - Stable Diffusion models
- `ComfyUI/models/loras/` - LoRA models
- `ComfyUI/models/vae/` - VAE models
- `ComfyUI/models/controlnet/` - ControlNet models
- `ComfyUI/models/upscale_models/` - Upscaler models
- `ComfyUI/models/embeddings/` - Textual Inversions
- `ComfyUI/models/clip/` - CLIP models
- `ComfyUI/models/unknown/` - Uncertain detections

## Troubleshooting

### "File exists" warning
The node skips existing files by default. Delete the old file first to re-download.

### Wrong folder detection
1. Check `models/unknown/` folder
2. Manually specify model type instead of "auto"
3. The file will still work - ComfyUI scans subfolders

### Download fails
- Verify the URL is a direct download link (not a webpage)
- Check network connection
- Some sites require authentication (not supported yet)

### Node doesn't appear
```bash
# Verify installation
ls /workspace/ComfyUI/custom_nodes/comfyui-model-downloader/

# Should show:
# __init__.py
# cloud_model_downloader.py
# requirements.txt

# Restart ComfyUI with verbose flag
python main.py --verbose
# Look for: "Loading custom node: comfyui-model-downloader"
```

## Requirements

- Python 3.8+
- ComfyUI
- `requests` library (see requirements.txt)

## Known Limitations

- No authentication support (public URLs only)
- No torrent/magnet links
- No automatic URL extraction from model pages (use direct links)
- Overwrites not implemented (skips existing files)

## Roadmap

- [ ] Authentication support (API keys, tokens)
- [ ] Resume interrupted downloads
- [ ] Batch download multiple URLs
- [ ] Integration with model browsers
- [ ] Overwrite options (skip/replace/rename)

## Contributing

Contributions welcome! Please:
1. Test your changes with various model types
2. Maintain the detection confidence system
3. Add logging for debugging

## License

MIT License - See LICENSE file

## Credits

Created for ComfyUI community
Detection logic inspired by safetensors specification

## Support

- Issues: https://github.com/yourusername/comfyui-model-downloader/issues
- ComfyUI: https://github.com/comfyanonymous/ComfyUI
