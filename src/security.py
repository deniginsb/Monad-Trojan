"""
Security Module - Handles encryption and decryption of sensitive data
CRITICAL: This module implements Fernet symmetric encryption for private keys
"""
import os
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

load_dotenv()

class SecurityManager:
    """Manages encryption and decryption of sensitive data using Fernet"""
    
    def __init__(self):
        """Initialize the security manager with master encryption key"""
        master_key = os.getenv('MASTER_ENCRYPTION_KEY')
        
        if not master_key:
            raise ValueError(
                "MASTER_ENCRYPTION_KEY not found in environment variables. "
                "Generate one using: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        
        try:
            self.fernet = Fernet(master_key.encode())
        except Exception as e:
            raise ValueError(f"Invalid MASTER_ENCRYPTION_KEY format: {e}")
    
    def encrypt_data(self, plaintext: str) -> str:
        """
        Encrypt sensitive data (e.g., private key)
        
        Args:
            plaintext: Data to encrypt (e.g., private key as string)
            
        Returns:
            Encrypted data as base64-encoded string
        """
        try:
            encrypted_bytes = self.fernet.encrypt(plaintext.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            raise Exception(f"Encryption failed: {e}")
    
    def decrypt_data(self, ciphertext: str) -> str:
        """
        Decrypt sensitive data (e.g., private key)
        
        Args:
            ciphertext: Encrypted data as base64-encoded string
            
        Returns:
            Decrypted plaintext string
            
        Raises:
            InvalidToken: If decryption fails (wrong key or corrupted data)
        """
        try:
            decrypted_bytes = self.fernet.decrypt(ciphertext.encode())
            return decrypted_bytes.decode()
        except InvalidToken:
            raise Exception("Decryption failed: Invalid token or wrong encryption key")
        except Exception as e:
            raise Exception(f"Decryption failed: {e}")
    
    def secure_delete(self, variable_name: str, local_vars: dict) -> None:
        """
        Securely delete a variable from memory
        
        Args:
            variable_name: Name of the variable to delete
            local_vars: locals() dictionary from calling scope
        """
        if variable_name in local_vars:
            local_vars[variable_name] = None
            del local_vars[variable_name]

def generate_new_encryption_key() -> str:
    """
    Generate a new Fernet encryption key
    
    Returns:
        Base64-encoded encryption key as string
    """
    return Fernet.generate_key().decode()

# Global security manager instance
security_manager = SecurityManager()

def encrypt_private_key(private_key: str) -> str:
    """
    Encrypt a private key for secure storage
    
    Args:
        private_key: Private key as hex string (with or without 0x prefix)
        
    Returns:
        Encrypted private key as base64 string
    """
    if not private_key:
        raise ValueError("Private key cannot be empty")
    
    # Normalize private key format
    if not private_key.startswith('0x'):
        private_key = '0x' + private_key
    
    return security_manager.encrypt_data(private_key)

def decrypt_private_key(encrypted_key: str) -> str:
    """
    Decrypt a private key for transaction signing
    WARNING: Decrypted key exists in memory temporarily - use and delete immediately
    
    Args:
        encrypted_key: Encrypted private key as base64 string
        
    Returns:
        Decrypted private key as hex string
    """
    if not encrypted_key:
        raise ValueError("Encrypted key cannot be empty")
    
    return security_manager.decrypt_data(encrypted_key)
