from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import os
from pathlib import Path

KEY_ENV_NAME = "SECURE_FINGERPRINT_ENCRYPTIONKEY"
KEY_FILE = Path(__file__).resolve().parent.parent / ".encryption_key"
NONCE_SIZE = 16


def loadKey() -> bytes:
    print("enc: start load key")
    configured = os.environ.get(KEY_ENV_NAME)
    if configured:
        key = configured.encode('utf-8')
        source = KEY_ENV_NAME
    else:
        key = loadOrCreateKeyFile()
        print(f'enc: found key ({key})')
        source = str(KEY_FILE)

    if len(key) not in AES.key_size:
        raise ValueError(f"{source} must be 16, 24 or 32 bytes long, got {len(key)}.")
    return key


def loadOrCreateKeyFile() -> bytes:
    try:
        descriptor = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        print('enc: key not found!! generating')
    except FileExistsError:
        return KEY_FILE.read_bytes()

    key = get_random_bytes(32)
    with os.fdopen(descriptor, 'wb') as file:
        file.write(key)
        print(f'enc: generated key ({key})')
    return key


class Encryption:
    def __init__(self):
        super().__init__()
        self.key = loadKey()

    def createEncryptedKey(self, value):
        if isinstance(value, str):
            value = value.encode('utf-8')
        nonce = get_random_bytes(NONCE_SIZE)
        cipher = AES.new(self.key, AES.MODE_EAX, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(value)
        return [nonce + ciphertext, tag]

    def decryptEncryptedKey(self, encrypted, tag):
        nonce, ciphertext = encrypted[:NONCE_SIZE], encrypted[NONCE_SIZE:]
        cipher = AES.new(self.key, AES.MODE_EAX, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)
