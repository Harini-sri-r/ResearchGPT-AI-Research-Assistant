import bcrypt


MAX_BCRYPT_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")

    if len(password_bytes) > MAX_BCRYPT_PASSWORD_BYTES:
        raise ValueError("Password is too long for bcrypt.")

    hashed_password = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt(rounds=12),
    )
    return hashed_password.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    password_bytes = password.encode("utf-8")
    hash_bytes = password_hash.encode("utf-8")

    if len(password_bytes) > MAX_BCRYPT_PASSWORD_BYTES:
        return False

    return bcrypt.checkpw(password_bytes, hash_bytes)
