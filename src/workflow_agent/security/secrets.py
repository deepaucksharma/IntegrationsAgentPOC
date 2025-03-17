import os
import logging
import base64
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pathlib import Path

logger = logging.getLogger(__name__)

class SecretsManager:
    """Secure secrets management system."""
    
    def __init__(self, key_file: Optional[str] = None):
        """
        Initialize the secrets manager.
        
        Args:
            key_file: Optional path to encryption key file
        """
        self.key_file = key_file or os.getenv('WORKFLOW_SECRETS_KEY_FILE')
        self.key = self._load_or_generate_key()
        self.cipher_suite = Fernet(self.key)
        
    def _load_or_generate_key(self) -> bytes:
        """Load existing key or generate a new one."""
        try:
            if self.key_file and os.path.exists(self.key_file):
                with open(self.key_file, 'rb') as f:
                    return f.read()
            else:
                # Generate a new key
                key = Fernet.generate_key()
                if self.key_file:
                    # Ensure directory exists
                    Path(self.key_file).parent.mkdir(parents=True, exist_ok=True)
                    # Save key
                    with open(self.key_file, 'wb') as f:
                        f.write(key)
                return key
        except Exception as e:
            logger.error(f"Error managing encryption key: {e}")
            raise
            
    def _derive_key(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """
        Derive an encryption key from a password.
        
        Args:
            password: Password to derive key from
            salt: Optional salt for key derivation
            
        Returns:
            Derived key bytes
        """
        if salt is None:
            salt = os.urandom(16)
            
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
        
    def encrypt(self, data: str) -> str:
        """
        Encrypt a string value.
        
        Args:
            data: String to encrypt
            
        Returns:
            Encrypted string
        """
        try:
            return self.cipher_suite.encrypt(data.encode()).decode()
        except Exception as e:
            logger.error(f"Error encrypting data: {e}")
            raise
            
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt an encrypted string.
        
        Args:
            encrypted_data: Encrypted string to decrypt
            
        Returns:
            Decrypted string
        """
        try:
            return self.cipher_suite.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.error(f"Error decrypting data: {e}")
            raise
            
    def encrypt_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt all string values in a dictionary.
        
        Args:
            data: Dictionary to encrypt
            
        Returns:
            Dictionary with encrypted values
        """
        encrypted = {}
        for key, value in data.items():
            if isinstance(value, str):
                encrypted[key] = self.encrypt(value)
            elif isinstance(value, dict):
                encrypted[key] = self.encrypt_dict(value)
            else:
                encrypted[key] = value
        return encrypted
        
    def decrypt_dict(self, encrypted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt all encrypted values in a dictionary.
        
        Args:
            encrypted_data: Dictionary with encrypted values
            
        Returns:
            Dictionary with decrypted values
        """
        decrypted = {}
        for key, value in encrypted_data.items():
            if isinstance(value, str):
                decrypted[key] = self.decrypt(value)
            elif isinstance(value, dict):
                decrypted[key] = self.decrypt_dict(value)
            else:
                decrypted[key] = value
        return decrypted
        
    def rotate_key(self) -> None:
        """Rotate the encryption key."""
        try:
            # Generate new key
            new_key = Fernet.generate_key()
            new_cipher_suite = Fernet(new_key)
            
            # Save new key
            if self.key_file:
                with open(self.key_file, 'wb') as f:
                    f.write(new_key)
                    
            # Update instance
            self.key = new_key
            self.cipher_suite = new_cipher_suite
            
        except Exception as e:
            logger.error(f"Error rotating encryption key: {e}")
            raise
            
    def secure_compare(self, a: str, b: str) -> bool:
        """
        Securely compare two strings to prevent timing attacks.
        
        Args:
            a: First string to compare
            b: Second string to compare
            
        Returns:
            True if strings are equal, False otherwise
        """
        if len(a) != len(b):
            return False
            
        result = 0
        for x, y in zip(a, b):
            result |= ord(x) ^ ord(y)
        return result == 0 