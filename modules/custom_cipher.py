from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import base64

class Secret:
    def __init__(self, key: bytes, iv: bytes):
        self.key = key
        self.iv = iv

class B64Cipher:
    def __init__(self, secret: Secret):
        self.secret = secret

    def decrypt(self, data: str) -> str:
        data = base64.b64decode(data)
        cipher = AES.new(self.secret.key, AES.MODE_CBC, self.secret.iv)
        decrypted_data = unpad(cipher.decrypt(data), AES.block_size)
        return decrypted_data.decode('utf-8')
