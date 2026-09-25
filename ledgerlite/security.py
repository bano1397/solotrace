import hashlib
import os


_ITERATIONS = 260_000
_HASH_NAME = "sha256"
_SALT_BYTES = 16


def hash_pin(pin: str) -> str:
    """Return a salted PBKDF2-HMAC-SHA256 hash of *pin* as a hex string."""
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(_HASH_NAME, pin.encode(), salt, _ITERATIONS)
    return salt.hex() + ":" + dk.hex()


def verify_pin(pin: str, stored_hash: str) -> bool:
    """Return True if *pin* matches *stored_hash*."""
    try:
        salt_hex, dk_hex = stored_hash.split(":")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac(_HASH_NAME, pin.encode(), salt, _ITERATIONS)
    return dk.hex() == dk_hex
