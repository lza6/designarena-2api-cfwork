# -*- coding: utf-8 -*-
import os
from cryptography.fernet import Fernet

KEY_FILE = "secret.key"

def _get_or_create_key():
    auth_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "auth")
    os.makedirs(auth_dir, exist_ok=True)
    key_path = os.path.join(auth_dir, "secret.key")
    legacy_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "secret.key")
    
    # v7.8: Migrate legacy key
    if os.path.exists(legacy_path) and not os.path.exists(key_path):
        try:
            import shutil
            shutil.move(legacy_path, key_path)
        except: pass

    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)
        return key

_fernet = Fernet(_get_or_create_key())

def encrypt_token(token: str) -> str:
    if not token: return ""
    return _fernet.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    if not encrypted_token: return ""
    try:
        return _fernet.decrypt(encrypted_token.encode()).decode()
    except:
        # Fallback for old plain-text tokens during migration
        return encrypted_token
