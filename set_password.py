#!/usr/bin/env python3
"""Set the dashboard login. Run it where the dashboard runs:  python set_password.py you@gmail.com
The password is typed at a hidden prompt and stored only as a salted scrypt hash in data/auth.json."""
import getpass
import sys

import webauth

if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else input("Email: ")
    pw = getpass.getpass("New password (10+ characters): ")
    if pw != getpass.getpass("Repeat it: "):
        sys.exit("The two passwords differ, nothing saved.")
    try:
        webauth.set_password(email, pw)
    except ValueError as e:
        sys.exit(str(e))
    print("Saved. Everyone is signed out; sign in again with the new password.")
