import subprocess
import os
import json
import base64
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

class ConfigManager:
    def __init__(self, config_dir=None):
        if config_dir is None:
            # Use the custom node directory
            config_dir = Path(__file__).parent
        
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "model_downloader_config.json"
        self.key_file = self.config_dir / ".model_downloader.key"
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize or load encryption key
        self._init_encryption_key()
    
    def _init_encryption_key(self):
        """Initialize or load the encryption key"""
        if not self.key_file.exists():
            # Generate new key
            key = Fernet.generate_key()
            self.key_file.write_bytes(key)
            # Add to .gitignore
            self._add_to_gitignore()
        
        # Load key
        key = self.key_file.read_bytes()
        self.cipher = Fernet(key)
    
    def _add_to_gitignore(self):
        """Add config files to .gitignore"""
        gitignore = self.config_dir / ".gitignore"
        ignore_entries = [
            ".model_downloader.key",
            "model_downloader_config.json",
            "__pycache__/",
            "*.pyc"
        ]
        
        existing = set()
        if gitignore.exists():
            existing = set(gitignore.read_text().splitlines())
        
        new_entries = [entry for entry in ignore_entries if entry not in existing]
        if new_entries:
            with open(gitignore, 'a') as f:
                f.write('\n' + '\n'.join(new_entries) + '\n')
    
    def encrypt_data(self, data):
        """Encrypt data dictionary"""
        json_str = json.dumps(data)
        encrypted = self.cipher.encrypt(json_str.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt_data(self, encrypted_str):
        """Decrypt data to dictionary"""
        encrypted = base64.b64decode(encrypted_str.encode())
        decrypted = self.cipher.decrypt(encrypted)
        return json.loads(decrypted.decode())
    
    def load_config(self):
        """Load and decrypt config file"""
        if not self.config_file.exists():
            return {"last_used_remote": None, "remotes": {}}
        
        try:
            encrypted_data = self.config_file.read_text()
            return self.decrypt_data(encrypted_data)
        except Exception as e:
            print(f"Error loading config: {e}")
            return {"last_used_remote": None, "remotes": {}}
    
    def save_config(self, config):
        """Encrypt and save config file"""
        encrypted_data = self.encrypt_data(config)
        self.config_file.write_text(encrypted_data)
    
    def save_remote(self, remote_name, remote_config):
        """Save or update remote configuration"""
        config = self.load_config()
        
        # Update or add remote
        config["remotes"][remote_name] = remote_config
        config["last_used_remote"] = remote_name
        
        self.save_config(config)
        return True
    
    def get_remote(self, remote_name=None):
        """Get remote configuration by name, or last used remote"""
        config = self.load_config()
        
        if remote_name:
            return config["remotes"].get(remote_name)
        elif config["last_used_remote"]:
            return config["remotes"].get(config["last_used_remote"])
        else:
            return None
    
    def list_remotes(self):
        """List all saved remotes"""
        config = self.load_config()
        return list(config["remotes"].keys())


class ModelDownloaderNode:
    # Comprehensive list of rclone providers
    RCLONE_PROVIDERS = [
        "s3", "b2", "google cloud storage", "azureblob", "dropbox", "ftp", "http", "webdav",
        "onedrive", "box", "mega", "pcloud", "putio", "seafile", "sharefile", "sugarsync",
        "yandex", "hubic", "jottacloud", "koofr", "mailru", "premiumize", "tardigrade",
        "union", "chunker", "crypt", "hasher", "cache", "alias", "local", "chacha", "null",
        "compress", "combine", "drive", "opendrive", "hidrive", "internetarchive", "mailru",
        "memset", "openstack", "qingstor", "stackpath", "vultr", "wasabi", "backblaze",
        "digitalocean", "dreamhost", "gcs", "ibmcos", "idrive", "ionos", "linode", "oracle",
        "scaleway", "storj", "tencent", "ucloud", "ceph", "minio", "petabox", "swift",
        "obs", "oss", "cos", "ks3", "eos", "gphotos", "photos", "smb", "nfs", "sftp",
        "ftp", "ftps", "dav", "webdav", "http", "https", "s3ql", "storj", "tardigrade"
    ]
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": ("STRING", {
                    "multiline": False,
                    "default": ""
                }),
                "destination": (["Local Pod", "Cloud Storage"], {
                    "default": "Local Pod"
                }),
            },
            "optional": {
                "remote_name": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "tooltip": "Name for this remote configuration (e.g., 'myb2', 'mys3')"
                }),
                "provider": (cls.RCLONE_PROVIDERS, {
                    "default": "s3",
                    "tooltip": "Cloud storage provider"
                }),
                "access_key_id": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "tooltip": "Access key ID for cloud storage"
                }),
                "secret_access_key": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "tooltip": "Secret access key for cloud storage",
                    "password": True
                }),
                "bucket": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "tooltip": "Bucket name"
                }),
                "endpoint": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "tooltip": "Custom endpoint URL (optional)"
                }),
                "region": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "tooltip": "Region for S3-compatible storage (optional)"
                }),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("file_path",)
    FUNCTION = "download_model"
    CATEGORY = "utils"
    OUTPUT_NODE = True
    
    def __init__(self):
        self.config_manager = ConfigManager()
    
    def _extract_filename(self, url):
        """Extract filename from URL"""
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        
        if not filename:
            # If no filename in URL, use a default
            filename = "downloaded_model.safetensors"
        
        return filename
    
    def _setup_rclone_env(self, remote_name, remote_config):
        """Setup rclone environment variables for dynamic configuration"""
        # Clear any existing RCLONE_CONFIG_* environment variables for this remote
        prefix = f"RCLONE_CONFIG_{remote_name.upper()}_"
        for key in list(os.environ.keys()):
            if key.startswith(prefix):
                del os.environ[key]
        
        # Set provider type
        os.environ[f'RCLONE_CONFIG_{remote_name.upper()}_TYPE'] = remote_config['provider']
        
        # Set credentials
        if 'access_key_id' in remote_config:
            os.environ[f'RCLONE_CONFIG_{remote_name.upper()}_ACCESS_KEY_ID'] = remote_config['access_key_id']
        if 'secret_access_key' in remote_config:
            os.environ[f'RCLONE_CONFIG_{remote_name.upper()}_SECRET_ACCESS_KEY'] = remote_config['secret_access_key']
        
        # Set optional fields
        if 'bucket' in remote_config and remote_config['bucket']:
            os.environ[f'RCLONE_CONFIG_{remote_name.upper()}_BUCKET'] = remote_config['bucket']
        if 'endpoint' in remote_config and remote_config['endpoint']:
            os.environ[f'RCLONE_CONFIG_{remote_name.upper()}_ENDPOINT'] = remote_config['endpoint']
        if 'region' in remote_config and remote_config['region']:
            os.environ[f'RCLONE_CONFIG_{remote_name.upper()}_REGION'] = remote_config['region']
        
        # Provider-specific configurations
        provider = remote_config['provider'].lower()
        if provider == 's3':
            os.environ[f'RCLONE_CONFIG_{remote_name.upper()}_PROVIDER'] = 'AWS'
        elif provider == 'google cloud storage':
            os.environ[f'RCLONE_CONFIG_{remote_name.upper()}_PROVIDER'] = 'GCS'
        elif provider == 'azureblob':
            os.environ[f'RCLONE_CONFIG_{remote_name.upper()}_PROVIDER'] = 'AzureBlob'
    
    def _validate_cloud_credentials(self, remote_name, provider, access_key_id, secret_access_key, bucket):
        """Validate required fields for cloud storage"""
        if not remote_name:
            raise ValueError("Remote name is required for cloud storage")
        
        if not provider:
            raise ValueError("Provider is required for cloud storage")
        
        if not access_key_id or not secret_access_key:
            # Check if we have saved credentials
            saved_config = self.config_manager.get_remote(remote_name)
            if not saved_config:
                raise ValueError("No credentials provided and no saved configuration found")
        
        if not bucket:
            raise ValueError("Bucket name is required for cloud storage")
        
        return True
    
    def download_model(self, url, destination, remote_name="", provider="s3", 
                      access_key_id="", secret_access_key="", bucket="", 
                      endpoint="", region=""):
        # Extract filename from URL
        filename = self._extract_filename(url)
        
        # Check if rclone is installed
        try:
            subprocess.run(['rclone', '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise Exception("rclone command not found. Please install rclone.")
        
        # Determine destination path based on selection
        if destination == "Local Pod":
            # Use folder_paths to get the checkpoints directory
            try:
                checkpoints_dir = folder_paths.get_folder_paths("checkpoints")[0]
            except:
                # Fallback to default path
                checkpoints_dir = "/workspace/ComfyUI/models/checkpoints"
            
            # Create directory if needed
            os.makedirs(checkpoints_dir, exist_ok=True)
            
            destination_path = os.path.join(checkpoints_dir, filename)
            
            # Run rclone copyurl command
            try:
                result = subprocess.run(
                    ['rclone', 'copyurl', url, destination_path],
                    capture_output=True,
                    text=True,
                    check=True
                )
                print(f"Download successful: {result.stdout}")
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr if e.stderr else "Unknown error"
                print(f"Download failed: {error_msg}")
                raise Exception(f"Failed to download model: {error_msg}")
        
        elif destination == "Cloud Storage":
            # Validate cloud credentials
            self._validate_cloud_credentials(remote_name, provider, access_key_id, secret_access_key, bucket)
            
            # Prepare remote configuration
            remote_config = {
                'provider': provider,
                'access_key_id': access_key_id,
                'secret_access_key': secret_access_key,
                'bucket': bucket,
                'endpoint': endpoint,
                'region': region
            }
            
            # Check if we have credentials provided or need to use saved ones
            if access_key_id and secret_access_key:
                # Save credentials to config
                self.config_manager.save_remote(remote_name, remote_config)
                print(f"Saved credentials for remote: {remote_name}")
            else:
                # Use saved credentials
                saved_config = self.config_manager.get_remote(remote_name)
                if not saved_config:
                    raise Exception("No saved credentials found. Please provide credentials or configure cloud storage first.")
                
                # Update remote_config with saved values
                remote_config.update(saved_config)
                print(f"Using saved credentials for remote: {remote_name}")
            
            # Setup rclone environment variables
            self._setup_rclone_env(remote_name, remote_config)
            
            # Destination path for cloud storage
            destination_path = f"{remote_name}:{bucket}/{filename}"
            
            # Run rclone copyurl command
            try:
                result = subprocess.run(
                    ['rclone', 'copyurl', url, destination_path],
                    capture_output=True,
                    text=True,
                    check=True
                )
                print(f"Upload to cloud storage successful: {result.stdout}")
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr if e.stderr else "Unknown error"
                print(f"Upload failed: {error_msg}")
                raise Exception(f"Failed to upload to cloud storage: {error_msg}")
        
        else:
            raise ValueError(f"Unknown destination: {destination}")
        
        # Return the file path
        return (destination_path,)


# Node export
NODE_CLASS_MAPPINGS = {
    "ModelDownloaderNode": ModelDownloaderNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModelDownloaderNode": "Model Downloader"
}