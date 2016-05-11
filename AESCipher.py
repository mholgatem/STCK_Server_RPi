import base64

from Crypto import Random
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from pkcs7 import PKCS7Encoder as PK

BS = 16
pad = lambda s: s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
unpad = lambda s : s[0:-ord(s[-1])]


class AESCipher:

    def __init__( self, key, salt, ignore = False):
        self.key = PBKDF2(key, salt, 32, 1000)
        self.salt = PBKDF2(key, salt, 32 + 16, 1000)[32:]
        self.ignore = ignore

    def encrypt( self, raw ):
        if self.ignore:
            return raw
        e = PK(16)
        raw = e.encode(raw.encode('utf-16'))
        iv = self.salt
        cipher = AES.new( self.key, AES.MODE_CBC, iv )
        return base64.b64encode( cipher.encrypt( raw ) )

    def decrypt( self, enc ):
        if self.ignore:
            return enc
        enc = base64.b64decode(enc)
        iv = self.salt
        cipher = AES.new(self.key, AES.MODE_CBC, iv )
        return unpad(cipher.decrypt( enc )).decode('utf-16')