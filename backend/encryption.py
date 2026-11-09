from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import os

class Encryption:
    def __init__(self):
        super().__init__()
        if  "SECURE_FINGERPRINT_ENCRYPTIONKEY" != os.environ: # check if encryption key exists.
            os.environ.setdefault("SECURE_FINGERPRINT_ENCRYPTIONKEY", str(get_random_bytes(16)))
        self.key = str(os.environ.get("SECURE_FINGERPRINT_ENCRYPTIONKEY")).encode('utf-8')
        self.cipher = AES.new(self.key, AES.MODE_EAX)

    def createEncryptedKey(self, value):
        ciphertext, tag = self.cipher.encrypt_and_digest(value)
        return [ciphertext, tag]

    def decryptEncryptedKey(self, cipher, tag):
        cipher_dec = AES.new(self.key, AES.MODE_EAX, cipher.nonce)
        return cipher_dec.decrypt_and_verify(cipher, tag)