import os
import hashlib
from pathlib import Path

BASE_DIR = Path("artifact_store/objects")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()





def open_object(sha256: str, mode="rb"):
    path = artifact_path(sha256)
    if not path.exists():
        raise FileNotFoundError(f"Artifact {sha256} not found")
    return open(path, mode)



def artifact_path(sha256: str) -> str:
    path = os.path.join(
        BASE_DIR,
        sha256[:2],
        sha256[2:4],
    )
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, sha256)


def store_attachment(payload: bytes) -> str:
    sha = sha256_bytes(payload)
    path = artifact_path(sha)

    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(payload)

    return sha
