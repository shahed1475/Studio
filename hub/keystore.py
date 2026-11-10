"""Each creator's own AI key (OpenRouter), stored encrypted for their account only.

Fernet (the `cryptography` library: AES-128-CBC with an HMAC, authenticated) under one server master key, in a mode-600 file `data/hub/keystore.key` made exclusively on
first use, or `HUB_KEYSTORE_KEY` in the environment for a server. The encrypted text starts with the account id, so a row copied to another account does not decrypt.
Nothing here returns, logs or audits a key: `status` says only that one is set. If the master key is lost the stored keys cannot be read and the creator adds theirs again."""
import os
import re
import time
from pathlib import Path

import config
from cryptography.fernet import Fernet, InvalidToken

from . import auth, db

MASTER_FILE = config.ROOT / "data" / "hub" / "keystore.key"
KEY_SHAPE = re.compile(r"^sk-or-[A-Za-z0-9_-]{16,200}$")
MODEL_SHAPE = re.compile(r"^[A-Za-z0-9._-]{1,60}/[A-Za-z0-9._:-]{1,80}$")


def _fernet() -> Fernet:
    env = os.environ.get("HUB_KEYSTORE_KEY", "").strip()
    if env:
        return Fernet(env.encode())
    path = Path(MASTER_FILE)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(Fernet.generate_key())
        except FileExistsError:  # two requests at once: the other one made it
            pass
    return Fernet(path.read_bytes().strip())


def clean_key(raw) -> str:
    key = str(raw or "").strip().strip("\"'").strip()
    if not KEY_SHAPE.match(key):
        raise ValueError("That is not the shape of an OpenRouter key (it starts with sk-or-).")
    return key


def clean_model(raw) -> str:
    model = str(raw or "").strip()
    if not MODEL_SHAPE.match(model):
        raise ValueError("The model must look like vendor/name; copy it from openrouter.ai/models.")
    return model


def set_key(account_id: str, key, model, now: float | None = None) -> None:
    now = time.time() if now is None else now
    key, model = clean_key(key), clean_model(model)
    token = _fernet().encrypt(f"{account_id}\n{key}".encode())
    with db.tx() as con:
        con.execute("insert into account_keys(account_id,token,model,added_at) values(?,?,?,?) on conflict(account_id) do update set "
                    "token=excluded.token, model=excluded.model, added_at=excluded.added_at", (account_id, token, model, now))
        auth._audit(con, "key_set", "ok", now, account_id=account_id)


def get(account_id: str) -> dict | None:
    """{key, model} for the model caller only. None when no key is stored or it cannot be read (master key lost, row from another account)."""
    with db.read() as con:
        row = con.execute("select token, model from account_keys where account_id=?", (account_id,)).fetchone()
    if not row:
        return None
    try:
        plain = _fernet().decrypt(bytes(row["token"])).decode()
    except (InvalidToken, ValueError):
        return None
    owner, _, key = plain.partition("\n")
    return {"key": key, "model": row["model"]} if owner == account_id and key else None


def status(account_id: str) -> dict:
    with db.read() as con:
        row = con.execute("select model, added_at from account_keys where account_id=?", (account_id,)).fetchone()
    return {"set": True, "model": row["model"], "added_at": row["added_at"]} if row else {"set": False, "model": "", "added_at": None}


def remove(account_id: str, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    with db.tx() as con:
        gone = con.execute("delete from account_keys where account_id=?", (account_id,)).rowcount > 0
        if gone:
            auth._audit(con, "key_removed", "ok", now, account_id=account_id)
    return gone
