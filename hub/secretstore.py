"""A private place for the hub's secrets: the mail password and the Google client id.

One small env-style file (`KEY=value` per line), `~/.config/nightloom/hub.env` by default (HUB_SECRETS_FILE changes it), mode 600 in a folder of mode 700,
never inside a git work tree. `python -m hub.configure` writes it from a terminal prompt; `hub.server` reads it at start with `load()`.
Rules (backend-design security discipline): only the names in ALLOWED; a value is one line; a write is atomic (a power cut leaves the old file or the new one,
never half); a file that other users can read, that belongs to someone else or that is a symbolic link is ignored, with the reason but never a value;
a real environment variable beats the file; no function here returns, prints or puts a secret in an error."""
import os
import stat
import tempfile
from pathlib import Path

ALLOWED = ("HUB_SMTP_HOST", "HUB_SMTP_PORT", "HUB_SMTP_USER", "HUB_SMTP_PASSWORD", "HUB_MAIL_FROM", "HUB_GOOGLE_CLIENT_ID")
MAX_VALUE = 512
REPO = Path(__file__).resolve().parent.parent
HEADER = "# Nightloom hub secrets. Private (mode 600). Never commit, copy into chat or share.\n"


class SecretError(ValueError):
    """A refusal. Its text names a setting or a rule, never a value."""


def default_path() -> Path:
    custom = os.environ.get("HUB_SECRETS_FILE", "").strip()
    return Path(custom).expanduser() if custom else Path.home() / ".config" / "nightloom" / "hub.env"


def _check(values) -> dict:
    if not isinstance(values, dict) or not values:
        raise SecretError("nothing to save")
    clean = {}
    for name, value in values.items():
        if name not in ALLOWED:
            raise SecretError(f"{name!r} is not a setting the hub stores")
        value = "" if value is None else str(value)
        if any(c in value for c in "\r\n\x00"):
            raise SecretError(f"{name} must be a single line without control characters")
        if len(value) > MAX_VALUE:
            raise SecretError(f"{name} is longer than {MAX_VALUE} characters")
        clean[name] = value
    return clean


def _in_git_work_tree(target: Path) -> bool:
    home = Path.home().resolve()
    for ancestor in target.parents:
        if ancestor == home:
            break  # a dotfiles repository in $HOME does not make ~/.config/nightloom unsafe
        if (ancestor / ".git").exists():
            return True
    return False


def _checked_target(path) -> Path:
    path = Path(path).expanduser()
    if path.is_symlink():
        raise SecretError("the secrets file is a symbolic link; remove the link first")
    target = path.parent.resolve() / path.name
    if target.is_relative_to(REPO) or _in_git_work_tree(target):
        raise SecretError("the secrets file must live outside any git work tree (default: ~/.config/nightloom/hub.env)")
    return target


def _open_safely(path, require_private: bool = True) -> tuple[str, str]:
    """(text, "") when the file is missing (text empty) or fine; ("", reason) when it must not be trusted.
    The checks run on the open file, so swapping the file between the check and the read cannot fool them."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return "", ""
    except OSError:
        return "", "it is a symbolic link or cannot be opened"
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return "", "it is not a regular file"
        if hasattr(os, "getuid") and st.st_uid != os.getuid():
            return "", "it belongs to another user"
        if require_private and st.st_mode & 0o077:
            return "", f"other users can read it; run: chmod 600 {path}"
        with os.fdopen(fd, "r", encoding="utf-8") as f:
            fd = -1
            return f.read(65536), ""
    finally:
        if fd != -1:
            os.close(fd)


def _parse(text: str) -> dict:
    out = {}
    for line in text.split("\n"):
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() in ALLOWED:
            out[name.strip()] = value
    return out


def _fsync_folder(folder: Path) -> None:
    try:
        fd = os.open(folder, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def save(values: dict, path=None) -> Path:
    """Store values (merged with what is already there). Atomic; the file is created private from the first byte."""
    clean = _check(values)
    target = _checked_target(path or default_path())
    folder = target.parent
    created = not folder.exists()
    os.makedirs(folder, mode=0o700, exist_ok=True)
    if created:
        os.chmod(folder, 0o700)  # only a folder we made; an existing folder keeps its owner's choice
    text, why = _open_safely(target, require_private=False)
    if why:
        raise SecretError(f"cannot update the existing secrets file: {why}")
    merged = {**_parse(text), **clean}
    fd, tmp = tempfile.mkstemp(prefix=".hub.env.", dir=folder)  # created with mode 600, exclusively
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(HEADER + "".join(f"{k}={merged[k]}\n" for k in ALLOWED if k in merged))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
    _fsync_folder(folder)
    return target


def load(path=None, environ=None) -> dict:
    """Put the file's settings into the environment (only names not already set). Returns {"loaded": [names], "ignored": reason}."""
    environ = os.environ if environ is None else environ
    path = Path(path).expanduser() if path else default_path()
    text, why = _open_safely(path)
    if why:
        return {"loaded": [], "ignored": why}
    loaded = []
    for name, value in _parse(text).items():
        if value and not str(environ.get(name, "")).strip():
            environ[name] = value
            loaded.append(name)
    return {"loaded": loaded, "ignored": ""}


def status(path=None, environ=None) -> dict:
    """Which settings are present, from the environment or the file. Names and yes/no only, never a value."""
    environ = os.environ if environ is None else environ
    path = Path(path).expanduser() if path else default_path()
    text, why = _open_safely(path)
    from_file = {} if why else _parse(text)
    return {name: bool(str(environ.get(name, "")).strip() or from_file.get(name, "").strip()) for name in ALLOWED}
