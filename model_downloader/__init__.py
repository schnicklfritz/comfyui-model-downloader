import subprocess
import os
import json
import base64
import urllib.request
import sys
from urllib.parse import urlparse
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Try to import folder_paths (ComfyUI specific)
try:
    import folder_paths
    FOLDER_PATHS_AVAILABLE = True
except ImportError:
    FOLDER_PATHS_AVAILABLE = False

# Check if rclone is available
def check_rclone():
    try:
        subprocess.run(['rclone', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

RCLONE_AVAILABLE = check_rclone()

class ConfigManager:
    def __init__(self, config_dir=None):
        if config_dir is None:
            config_dir = Path(__file__).parent
        
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "model_downloader_config.json"
        self.key_file = self.config_dir / ".model_downloader.key"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._init_encryption_key()
    
    def _init_encryption_key(self):
        if not self.key_file.exists():
            key = Fernet.generate_key()
            self.key_file.write_bytes(key)
            self._add_to_gitignore()
        
        key = self.key_file.read_bytes()
        self.cipher = Fernet(key)
    
    def _add_to_gitignore(self):
        gitignore = self.config_dir / ".gitignore"
        ignore_entries = [
            ".model_downloader.key",
            "model_downloader_config.json"
        ]
        
        existing = []
        if gitignore.exists():
            existing = gitignore.read_text().splitlines()
        
        with open(gitignore, 'a') as f:
            for entry in ignore_entries:
                if entry not in existing:
                    f.write(f"\n{entry}")
    
    def save_remote(self, name, config):
        all_config = self._load_config()
        encrypted_config = {}
        for key, value in config.items():
            if value and key in ['access_key_id', 'secret_access_key']:
                encrypted_config[key] = self.cipher.encrypt(value.encode()).decode()
            else:
                encrypted_config[key] = value
        
        all_config['remotes'] = all_config.get('remotes', {})
        all_config['remotes'][name] = encrypted_config
        self._save_config(all_config)
    
    def get_remote(self, name):
        all_config = self._load_config()
        remotes = all_config.get('remotes', {})
        if name not in remotes:
            return None
        
        config = remotes[name].copy()
        for key in ['access_key_id', 'secret_access_key']:
            if config.get(key):
                try:
                    config[key] = self.cipher.decrypt(config[key].encode()).decode()
                except:
                    pass
        
        return config
    
    def _load_config(self):
        if self.config_file.exists():
            return json.loads(self.config_file.read_text())
        return {}
    
    def _save_config(self, config):
        self.config_file.write_text(json.dumps(config, indent=2))


class ModelDownloaderNode:
    def __init__(self):
        self.config_manager = ConfigManager()
    
    @classmethod
    def INPUT_TYPES(cls):
        destinations = ["Local Pod"]
        if RCLONE_AVAILABLE:
            destinations.append("Cloud Storage")
        
        return {
            "required": {
                "url": ("STRING", {"default": "https://"}),
                "destination": (destinations,),
            },
            "optional": {
                "remote_name": ("STRING", {"default": "myremote"}),
                "provider": (["s3", "b2", "gcs", "azure"], {"default": "s3"}),
                "access_key_id": ("STRING", {"default": ""}),
                "secret_access_key": ("STRING", {"default": ""}),
                "bucket": ("STRING", {"default": ""}),
                "endpoint": ("STRING", {"default": ""}),
                "region": ("STRING", {"default": "us-east-1"}),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    FUNCTION = "download_model"
    CATEGORY = "Model Management"
    
    def _extract_filename(self, url):
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        return filename if filename else "downloaded_model.safetensors"
    
    def _download_with_progress(self, url, dest_path):
        """Download file with progress bar (no rclone needed)"""
        print(f"Downloading: {url}")
        print(f"To: {dest_path}")
        
        def progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            percent = min(downloaded * 100 / total_size, 100) if total_size > 0 else 0
            sys.stdout.write(f"\r[{'=' * int(percent/2):{50}}] {percent:.1f}%")
            sys.stdout.flush()
        
        try:
            urllib.request.urlretrieve(url, dest_path, progress)
            print("\n✓ Download complete")
        except Exception as e:
            raise Exception(f"Download failed: {str(e)}")
    
    def _validate_cloud_credentials(self, remote_name, provider, access_key_id, secret_access_key, bucket):
        if not remote_name:
            raise ValueError("Remote name is required")
        if not bucket:
            raise ValueError("Bucket name is required")
    
    def _setup_rclone_env(self, remote_name, config):
        env_vars = {
            f"RCLONE_CONFIG_{remote_name.upper()}_TYPE": config['provider'],
            f"RCLONE_CONFIG_{remote_name.upper()}_ACCESS_KEY_ID": config['access_key_id'],
            f"RCLONE_CONFIG_{remote_name.upper()}_SECRET_ACCESS_KEY": config['secret_access_key'],
        }
        
        if config.get('endpoint'):
            env_vars[f"RCLONE_CONFIG_{remote_name.upper()}_ENDPOINT"] = config['endpoint']
        if config.get('region'):
            env_vars[f"RCLONE_CONFIG_{remote_name.upper()}_REGION"] = config['region']
        
        os.environ.update(env_vars)
    
    def download_model(self, url, destination, remote_name="", provider="s3", 
                      access_key_id="", secret_access_key="", bucket="", 
                      endpoint="", region="us-east-1"):
        
        filename = self._extract_filename(url)
        
        if destination == "Local Pod":
            # Get ComfyUI checkpoints directory
            try:
                if FOLDER_PATHS_AVAILABLE:
                    checkpoints_dir = folder_paths.get_folder_paths("checkpoints")[0]
                else:
                    checkpoints_dir = "/root/ComfyUI/models/checkpoints"
            except:
                checkpoints_dir = "/root/ComfyUI/models/checkpoints"
            
            os.makedirs(checkpoints_dir, exist_ok=True)
            destination_path = os.path.join(checkpoints_dir, filename)
            
            # Use native Python download (no rclone required)
            self._download_with_progress(url, destination_path)
            print(f"✓ Saved to: {destination_path}")
        
        elif destination == "Cloud Storage":
            if not RCLONE_AVAILABLE:
                raise Exception("Cloud storage requires rclone. Install with: apt install rclone")
            
            # Validate cloud credentials
            self._validate_cloud_credentials(remote_name, provider, access_key_id, secret_access_key, bucket)
            
            remote_config = {
                'provider': provider,
                'access_key_id': access_key_id,
                'secret_access_key': secret_access_key,
                'bucket': bucket,
                'endpoint': endpoint,
                'region': region
            }
            
            if access_key_id and secret_access_key:
                self.config_manager.save_remote(remote_name, remote_config)
                print(f"✓ Saved credentials for: {remote_name}")
            else:
                saved_config = self.config_manager.get_remote(remote_name)
                if not saved_config:
                    raise Exception("No saved credentials. Please provide credentials.")
                remote_config.update(saved_config)
            
            self._setup_rclone_env(remote_name, remote_config)
            destination_path = f"{remote_name}:{bucket}/{filename}"
            
            try:
                result = subprocess.run(
                    ['rclone', 'copyurl', url, destination_path],
                    capture_output=True, text=True, check=True
                )
                print(f"✓ Uploaded to cloud: {result.stdout}")
            except subprocess.CalledProcessError as e:
                raise Exception(f"Cloud upload failed: {e.stderr}")
        
        else:
            raise ValueError(f"Unknown destination: {destination}")
        
        return (destination_path,)


NODE_CLASS_MAPPINGS = {
    "ModelDownloaderNode": ModelDownloaderNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModelDownloaderNode": "Model Downloader"
}
