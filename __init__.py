import os
import requests
import sys
from urllib.parse import urlparse
from pathlib import Path

# Try to import folder_paths (ComfyUI specific)
try:
    import folder_paths
    FOLDER_PATHS_AVAILABLE = True
except ImportError:
    FOLDER_PATHS_AVAILABLE = False


class ModelDownloaderNode:
    
    # Map model types to their folder paths
    MODEL_TYPES = {
        "checkpoints": "checkpoints",
        "loras": "loras",
        "vae": "vae",
        "embeddings": "embeddings",
        "controlnet": "controlnet",
        "upscale_models": "upscale_models",
        "clip": "clip",
        "clip_vision": "clip_vision",
        "style_models": "style_models",
        "unet": "unet"
    }
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": ("STRING", {"default": "https://", "multiline": False}),
                "model_type": (list(cls.MODEL_TYPES.keys()), {"default": "checkpoints"}),
            },
            "optional": {
                "filename": ("STRING", {"default": "", "multiline": False}),
                "auth_token": ("STRING", {"default": "", "multiline": False}),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("file_path",)
    FUNCTION = "download_model"
    CATEGORY = "Model Management"
    OUTPUT_NODE = True
    
    def _extract_filename(self, url, headers=None):
        """Extract filename from URL or Content-Disposition header"""
        # Try to get filename from Content-Disposition header
        if headers and 'Content-Disposition' in headers:
            import re
            cd = headers['Content-Disposition']
            filename_match = re.findall('filename="?(.+)"?', cd)
            if filename_match:
                return filename_match[0]
        
        # Fall back to URL parsing
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        return filename if filename else "downloaded_model.safetensors"
    
    def _get_model_folder(self, model_type):
        """Get the correct folder path for the model type"""
        if FOLDER_PATHS_AVAILABLE:
            try:
                folder_list = folder_paths.get_folder_paths(model_type)
                if folder_list:
                    return folder_list[0]
            except:
                pass
        
        # Fallback to default ComfyUI structure
        base_path = Path("/workspace/ComfyUI/models")
        return str(base_path / self.MODEL_TYPES[model_type])
    
    def _download_with_progress(self, url, dest_path, auth_token=""):
        """Download file with progress bar using requests"""
        print(f"\n{'='*60}")
        print(f"Downloading: {url}")
        print(f"To: {dest_path}")
        print(f"{'='*60}")
        
        # Set up headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Add authentication if provided
        if auth_token and auth_token.strip():
            headers['Authorization'] = f'Bearer {auth_token.strip()}'
        
        try:
            # Make request with timeout and stream enabled
            response = requests.get(
                url, 
                headers=headers, 
                stream=True, 
                timeout=30,  # 30 second timeout
                allow_redirects=True  # Follow redirects
            )
            response.raise_for_status()
            
            # Get total file size
            total_size = int(response.headers.get('content-length', 0))
            
            # Download with progress
            downloaded = 0
            block_size = 8192
            
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            percent = min(downloaded * 100 / total_size, 100)
                            bar_length = 50
                            filled = int(bar_length * percent / 100)
                            bar = '=' * filled + '-' * (bar_length - filled)
                            
                            downloaded_mb = downloaded / (1024 * 1024)
                            total_mb = total_size / (1024 * 1024)
                            
                            sys.stdout.write(f'\r[{bar}] {percent:.1f}% ({downloaded_mb:.1f}MB / {total_mb:.1f}MB)')
                            sys.stdout.flush()
            
            print("\n" + "="*60)
            print("✓ Download complete!")
            print("="*60 + "\n")
            
        except requests.exceptions.Timeout:
            raise Exception(f"Download timed out after 30 seconds. The server may be slow or the URL invalid.")
        except requests.exceptions.HTTPError as e:
            raise Exception(f"HTTP Error {e.response.status_code}: {e.response.reason}. Check if URL requires authentication.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Download failed: {str(e)}")
    
    def download_model(self, url, model_type, filename="", auth_token=""):
        """Download model to the appropriate ComfyUI folder"""
        
        # Validate URL
        if not url or url == "https://":
            raise ValueError("Please provide a valid URL")
        
        # Quick validation
        if not url.startswith(('http://', 'https://')):
            raise ValueError("URL must start with http:// or https://")
        
        # Determine filename
        if filename and filename.strip():
            final_filename = filename.strip()
        else:
            final_filename = self._extract_filename(url)
        
        # Get destination folder
        dest_folder = self._get_model_folder(model_type)
        os.makedirs(dest_folder, exist_ok=True)
        
        # Full destination path
        dest_path = os.path.join(dest_folder, final_filename)
        
        # Check if file already exists
        if os.path.exists(dest_path):
            print(f"⚠ File already exists: {dest_path}")
            print("Skipping download.")
            return (dest_path,)
        
        # Download the model
        self._download_with_progress(url, dest_path, auth_token)
        
        return (dest_path,)


NODE_CLASS_MAPPINGS = {
    "ModelDownloaderNode": ModelDownloaderNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModelDownloaderNode": "Model Downloader"
}
