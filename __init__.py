import os
import subprocess
import shutil
from pathlib import Path

try:
    import folder_paths
    COMFYUI_AVAILABLE = True
except ImportError:
    COMFYUI_AVAILABLE = False

try:
    from safetensors import safe_open
    SAFETENSORS_AVAILABLE = True
except ImportError:
    SAFETENSORS_AVAILABLE = False


class CloudModelDownloader:
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": ("STRING", {"default": "", "multiline": True}),
            },
            "optional": {
                "filename": ("STRING", {"default": ""}),
                "model_type": (["auto", "checkpoints", "loras", "vae", "controlnet", "embeddings", "upscale_models"], {"default": "auto"}),
                "rclone_remote": ("STRING", {"default": ""}),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("status",)
    FUNCTION = "download"
    CATEGORY = "model_management"
    OUTPUT_NODE = True
    
    def _extract_filename_from_url(self, url):
        """Extract filename from URL"""
        from urllib.parse import urlparse, unquote
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        # Remove query params if present
        filename = filename.split('?')[0]
        return unquote(filename) if filename else "model.safetensors"
    
    def _detect_model_type(self, filepath):
        """Detect model type from safetensors metadata or file characteristics"""
        
        if not SAFETENSORS_AVAILABLE:
            print("⚠ safetensors not available, using size heuristics")
            return self._detect_by_size(filepath)
        
        try:
            with safe_open(filepath, framework="pt") as f:
                metadata = f.metadata()
                
                if metadata:
                    # Check modelspec.architecture (Stability AI standard)
                    arch = metadata.get('modelspec.architecture', '').lower()
                    title = metadata.get('modelspec.title', '').lower()
                    
                    if 'lora' in arch or 'lora' in title:
                        return 'loras'
                    elif 'vae' in arch or 'vae' in title:
                        return 'vae'
                    elif 'controlnet' in arch or 'controlnet' in title:
                        return 'controlnet'
                    elif 'upscale' in arch or 'upscale' in title or 'esrgan' in title:
                        return 'upscale_models'
                    elif 'unet' in arch or 'checkpoint' in arch or 'sd' in arch:
                        return 'checkpoints'
                
                # Check tensor structure
                tensor_keys = list(f.keys())
                
                # LoRA detection
                if any('lora' in k.lower() for k in tensor_keys):
                    return 'loras'
                
                # VAE detection
                if any('vae' in k.lower() for k in tensor_keys):
                    return 'vae'
                
                # ControlNet detection
                if any('control' in k.lower() for k in tensor_keys):
                    return 'controlnet'
                
                # Small models are usually embeddings or LoRAs
                if len(tensor_keys) < 50:
                    return 'embeddings'
        
        except Exception as e:
            print(f"⚠ Metadata detection failed: {e}")
        
        # Fallback to size heuristics
        return self._detect_by_size(filepath)
    
    def _detect_by_size(self, filepath):
        """Fallback detection based on file size"""
        size_mb = os.path.getsize(filepath) / (1024 ** 2)
        
        if size_mb < 10:
            return 'embeddings'
        elif size_mb < 500:
            return 'loras'
        else:
            return 'checkpoints'
    
    def _get_model_folder(self, model_type):
        """Get ComfyUI folder path for model type"""
        if COMFYUI_AVAILABLE:
            try:
                folders = folder_paths.get_folder_paths(model_type)
                if folders:
                    return folders[0]
            except Exception as e:
                print(f"⚠ folder_paths failed: {e}")
        
        # Fallback paths
        base = Path("/workspace/ComfyUI/models")
        if not base.exists():
            base = Path.home() / "ComfyUI" / "models"
        
        return str(base / model_type)
    
    def download(self, url, filename="", model_type="auto", rclone_remote=""):
        """Download model and auto-sort to correct folder"""
        
        if not url or not url.strip():
            return ("❌ ERROR: No URL provided",)
        
        # Clean URL
        url = url.strip()
        
        # Determine filename
        if not filename or not filename.strip():
            filename = self._extract_filename_from_url(url)
        else:
            filename = filename.strip()
        
        print(f"\n{'='*60}")
        print(f"Cloud Model Downloader")
        print(f"{'='*60}")
        print(f"URL: {url[:80]}...")
        print(f"Filename: {filename}")
        
        # Download to temp location first
        temp_dir = "/tmp/comfyui_downloads"
        os.makedirs(temp_dir, exist_ok=True)
        temp_file = os.path.join(temp_dir, filename)
        
        print(f"Downloading to temp: {temp_file}")
        
        try:
            # Download with curl
            result = subprocess.run(
                ['curl', '-L', '-o', temp_file, '--progress-bar', url],
                capture_output=False,
                check=True
            )
        except subprocess.CalledProcessError as e:
            return (f"❌ Download failed: {str(e)}",)
        except FileNotFoundError:
            return ("❌ curl not found. Install curl first.",)
        
        # Detect model type if auto
        if model_type == "auto":
            print("🔍 Detecting model type...")
            detected_type = self._detect_model_type(temp_file)
            print(f"✓ Detected: {detected_type}")
        else:
            detected_type = model_type
            print(f"✓ Using forced type: {detected_type}")
        
        # Handle rclone upload
        if rclone_remote and rclone_remote.strip():
            remote_path = f"{rclone_remote.strip()}/models/{detected_type}/{filename}"
            print(f"📤 Uploading to rclone: {remote_path}")
            
            try:
                subprocess.run(
                    ['rclone', 'copyto', temp_file, remote_path, '--progress'],
                    check=True
                )
                os.remove(temp_file)
                return (f"✓ Uploaded to {remote_path}",)
            except subprocess.CalledProcessError as e:
                return (f"❌ rclone failed: {str(e)}",)
            except FileNotFoundError:
                return ("❌ rclone not found. Install rclone first.",)
        
        # Move to ComfyUI folder
        dest_folder = self._get_model_folder(detected_type)
        os.makedirs(dest_folder, exist_ok=True)
        dest_path = os.path.join(dest_folder, filename)
        
        # Check if already exists
        if os.path.exists(dest_path):
            print(f"⚠ File exists: {dest_path}")
            choice = "overwrite"  # or make this configurable
            if choice != "overwrite":
                os.remove(temp_file)
                return (f"⚠ Skipped - file exists: {dest_path}",)
        
        print(f"📁 Moving to: {dest_path}")
        shutil.move(temp_file, dest_path)
        
        print(f"{'='*60}")
        print(f"✓ SUCCESS")
        print(f"{'='*60}\n")
        
        return (f"✓ Downloaded to {detected_type}/{filename}",)


NODE_CLASS_MAPPINGS = {
    "CloudModelDownloader": CloudModelDownloader
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CloudModelDownloader": "Cloud Model Downloader"
}

