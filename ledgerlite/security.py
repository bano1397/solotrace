"""PIN hashing for LedgerLite (PBKDF2-HMAC-SHA256, salted, constant-time check).

Hash format: ``pbkdf2_sha256$<iterations>$<salt hex>$<hash hex>`` so the work
factor can be raised later without breaking stored hashes.  The default follows
the OWASP recommendation for PBKDF2-HMAC-SHA256 (600,000 iterations); tests set
``LEDGERLITE_PIN_ITERATIONS`` to a small number purely to keep the suite fast.
"""
import hashlib
import hmac
import os

_ALGORITHM = "pbkdf2_sha256"
_SALT_BYTES = 16
_DEFAULT_ITERATIONS = 600_000


def _iterations() -> int:
    return int(os.environ.get("LEDGERLITE_PIN_ITERATIONS", _DEFAULT_ITERATIONS))


def hash_pin(pin: str) -> str:
    """Return a salted PBKDF2-HMAC-SHA256 hash of *pin*."""
    iterations = _iterations()
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, iterations)
    return f"{_ALGORITHM}${iterations}${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored_hash: str) -> bool:
    """Return True if *pin* matches *stored_hash* (constant-time comparison)."""
    try:
        algorithm, iterations, salt_hex, digest_hex = stored_hash.split("$")
        if algorithm != _ALGORITHM:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        rounds = int(iterations)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, rounds)
    return hmac.compare_digest(candidate, expected)
