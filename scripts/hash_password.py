"""Generate a bcrypt hash for the OWNER_PASSWORD_HASH env var.

Usage:
    python scripts/hash_password.py
"""

import getpass

import bcrypt


def main() -> None:
    password = getpass.getpass("Owner password to hash: ")
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    print("\nOWNER_PASSWORD_HASH=" + hashed)


if __name__ == "__main__":
    main()
