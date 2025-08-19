# utils/file_utils.py
import os
from typing import Set, List

def ensure_dir(dirpath):
    os.makedirs(dirpath, exist_ok=True)

def append_line(path: str, line: str):
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def load_set_from_file(path: str) -> Set[str]:
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_lines(path: str, lines: List[str]):
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

