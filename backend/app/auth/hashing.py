from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Argon2id (argon2-cffi's default) is the current best-practice choice for
# password hashing: it's memory-hard, which makes GPU/ASIC brute-forcing far
# more expensive than a fast hash like bcrypt/scrypt at equivalent settings.
# Never hash passwords with a general-purpose hash (SHA-256, MD5, etc.) —
# those are designed to be fast, which is the opposite of what you want here.
_hasher = PasswordHasher()

# A tiny denylist of the most common leaked passwords. This is illustrative,
# not exhaustive — for a real deployment, check against a proper corpus like
# the "Have I Been Pwned" Pwned Passwords list (k-anonymity API, no plaintext
# password ever leaves the server).
_COMMON_PASSWORDS = {
    "password", "password123", "password1234", "123456", "12345678",
    "qwerty", "letmein", "admin123", "welcome1", "iloveyou", "changeme",
}

MIN_PASSWORD_LENGTH = 12


class WeakPasswordError(ValueError):
    pass


def validate_password_strength(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )
    if password.lower() in _COMMON_PASSWORDS:
        raise WeakPasswordError("Password is too common. Choose something less guessable.")


def hash_password(password: str) -> str:
    """Hash a plaintext password. The salt is generated automatically and
    embedded in the returned hash string — never store or manage salts
    separately."""
    return _hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        _hasher.verify(hashed_password, password)
    except VerifyMismatchError:
        return False
    return True


def needs_rehash(hashed_password: str) -> bool:
    """True if the stored hash was made with outdated parameters (e.g. after
    you raise Argon2's cost settings). Call after a successful verify and
    re-hash+save if True, so security upgrades roll out transparently as
    users log in."""
    return _hasher.check_needs_rehash(hashed_password)
