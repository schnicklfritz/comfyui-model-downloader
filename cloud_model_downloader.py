import os
import sys
import requests
import json
import tempfile
import shutil
from pathlib import Path

class CloudModelDownloader:
    """
    ComfyUI custom node for downloading models from cloud URLs
    """

    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "comfyui_downloads"
        self.temp_dir.mkdir(exist_ok=True)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": ("STRING", {
                    "multiline": False,
                    "default": ""
                }),
                "model_type": (["auto", "checkpoints", "loras", "vae", "controlnet", "upscale_models", "embeddings", "clip", "unknown"], {
                    "default": "auto"
                }),
                "filename": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "tooltip": "Optional: Override filename"
                })
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("status",)
    FUNCTION = "download_model"
    CATEGORY = "model_management"
    OUTPUT_NODE = True

    def download_model(self, url, model_type="auto", filename=""):
        """Main download function"""

        try:
            print("=" * 60)
            print("Cloud Model Downloader")
            print("=" * 60)
            print(f"URL: {url}...")

            # Determine filename
            if not filename:
                filename = self._extract_filename(url)

            print(f"Filename: {filename}")

            # Download to temp
            temp_path = self.temp_dir / filename
            print(f"Downloading to temp: {temp_path}")

            self._download_file(url, temp_path)

            # Detect model type if auto
            if model_type == "auto":
                print("🔍 Detecting model type...")
                model_type, confidence, reason = self._detect_model_type(temp_path, filename)
                print(f"✓ Detected: {model_type}")

                if confidence < 0.7:
                    print(f"⚠ Low confidence detection ({confidence:.1%})")
                    print(f"  Reason: {reason}")
                    print(f"  → Placing in models/{model_type}/ for manual review")

            # Move to final location
            final_path = self._get_model_path(model_type, filename)

            if final_path.exists():
                print(f"⚠ File exists: {final_path}")
                choice = "skip"  # For now, skip. Could add overwrite logic
            else:
                final_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(temp_path), str(final_path))
                print(f"✓ Saved to: {final_path}")

            return (f"Downloaded: {filename} → models/{model_type}/",)

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"❌ {error_msg}")
            return (error_msg,)

    def _extract_filename(self, url):
        """Extract filename from URL"""
        from urllib.parse import urlparse, unquote

        # Try to get from URL path
        parsed = urlparse(url)
        path = unquote(parsed.path)
        filename = os.path.basename(path)

        # Validate extension
        valid_exts = ['.safetensors', '.ckpt', '.pt', '.pth', '.bin']
        if not any(filename.endswith(ext) for ext in valid_exts):
            filename = "model.safetensors"

        return filename

    def _download_file(self, url, dest_path):
        """Download file with progress"""
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192

        with open(dest_path, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(block_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total_size:
                        progress = (downloaded / total_size) * 100
                        bar_length = 50
                        filled = int(bar_length * downloaded / total_size)
                        bar = '#' * filled + ' ' * (bar_length - filled)
                        print(f"\r[{bar}] {progress:.1f}%", end='', flush=True)

            print()  # New line after progress

    def _detect_model_type(self, file_path, filename):
        """
        Detect model type from file content
        Returns: (type, confidence, reason)
        """

        # Try safetensors metadata first
        if filename.endswith('.safetensors'):
            try:
                result = self._detect_from_safetensors(file_path)
                if result:
                    return result
            except Exception as e:
                print(f"  Could not read safetensors metadata: {e}")

        # Fall back to filename patterns
        result = self._detect_from_filename(filename)
        if result:
            return result

        # Fall back to file size (lowest confidence)
        return self._detect_from_size(file_path, filename)

    def _detect_from_safetensors(self, file_path):
        """Read safetensors header and detect from tensor names"""

        with open(file_path, 'rb') as f:
            # Read header length (first 8 bytes)
            length_bytes = f.read(8)
            header_length = int.from_bytes(length_bytes, 'little')

            # Read header JSON
            header_json = f.read(header_length).decode('utf-8')
            header = json.loads(header_json)

        # Get tensor names
        tensor_names = [k for k in header.keys() if k != '__metadata__']

        if not tensor_names:
            return None

        # Check metadata first
        metadata = header.get('__metadata__', {})
        if 'modelspec.architecture' in metadata:
            arch = metadata['modelspec.architecture'].lower()
            if 'vae' in arch:
                return ('vae', 0.95, 'metadata architecture contains VAE')
            if 'lora' in arch:
                return ('loras', 0.95, 'metadata architecture contains LoRA')

        # Check tensor name patterns
        first_tensors = tensor_names[:10]  # Check first 10 tensors

        # VAE patterns
        vae_patterns = ['encoder.', 'decoder.', 'quant_conv', 'post_quant_conv']
        if any(any(pattern in name for pattern in vae_patterns) for name in first_tensors):
            return ('vae', 0.9, 'tensor names match VAE patterns')

        # LoRA patterns
        lora_patterns = ['lora_unet', 'lora_te', '.lora_up.', '.lora_down.', '.alpha']
        if any(any(pattern in name for pattern in lora_patterns) for name in first_tensors):
            return ('loras', 0.9, 'tensor names match LoRA patterns')

        # Full model patterns
        model_patterns = ['model.diffusion_model', 'cond_stage_model', 'first_stage_model']
        if any(any(pattern in name for pattern in model_patterns) for name in first_tensors):
            return ('checkpoints', 0.9, 'tensor names match checkpoint patterns')

        # ControlNet patterns
        if any('control_model' in name for name in first_tensors):
            return ('controlnet', 0.9, 'tensor names match ControlNet patterns')

        # CLIP patterns
        if any('text_model' in name or 'embeddings' in name for name in first_tensors):
            if len(tensor_names) < 100:  # CLIP is relatively small
                return ('clip', 0.8, 'tensor names match CLIP patterns')

        return None

    def _detect_from_filename(self, filename):
        """Detect from filename patterns"""

        name_lower = filename.lower()

        # Strong indicators
        if 'vae' in name_lower:
            return ('vae', 0.8, 'filename contains "vae"')
        if 'lora' in name_lower:
            return ('loras', 0.8, 'filename contains "lora"')
        if 'controlnet' in name_lower or 'control_' in name_lower:
            return ('controlnet', 0.8, 'filename contains controlnet indicator')
        if 'upscale' in name_lower or 'esrgan' in name_lower or 'realesrgan' in name_lower:
            return ('upscale_models', 0.8, 'filename contains upscale indicator')
        if 'embedding' in name_lower or 'textual_inversion' in name_lower:
            return ('embeddings', 0.8, 'filename contains embedding indicator')
        if 'clip' in name_lower:
            return ('clip', 0.7, 'filename contains "clip"')

        return None

    def _detect_from_size(self, file_path, filename):
        """Detect from file size (lowest confidence)"""

        size_mb = os.path.getsize(file_path) / (1024 * 1024)

        # Size-based guessing (very approximate)
        if size_mb < 50:
            return ('unknown', 0.3, f'small file ({size_mb:.0f}MB) - unclear type')
        elif size_mb < 500:
            return ('unknown', 0.4, f'medium file ({size_mb:.0f}MB) - could be LoRA or VAE')
        elif size_mb < 3000:
            return ('unknown', 0.5, f'large file ({size_mb:.0f}MB) - could be checkpoint')
        else:
            return ('checkpoints', 0.6, f'very large file ({size_mb:.0f}MB) - likely checkpoint')

    def _get_model_path(self, model_type, filename):
        """Get final path for model"""

        # Get ComfyUI directory
        comfy_dir = Path(__file__).parent.parent.parent

        # Model type to folder mapping
        model_paths = {
            "checkpoints": "models/checkpoints",
            "loras": "models/loras",
            "vae": "models/vae",
            "controlnet": "models/controlnet",
            "upscale_models": "models/upscale_models",
            "embeddings": "models/embeddings",
            "clip": "models/clip",
            "unknown": "models/unknown"
        }

        folder = model_paths.get(model_type, "models/unknown")
        return comfy_dir / folder / filename

# ComfyUI node registration
NODE_CLASS_MAPPINGS = {
    "CloudModelDownloader": CloudModelDownloader
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CloudModelDownloader": "Cloud Model Downloader"
}
