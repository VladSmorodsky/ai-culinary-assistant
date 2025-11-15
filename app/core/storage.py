from __future__ import annotations
import json, os, tempfile, shutil, threading
from typing import Dict, Any

class FileKV:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)

    def read(self) -> Dict[str, Any]:
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}

    def write(self, data: Dict[str, Any]):
        with self._lock:
            tmpfd, tmppath = tempfile.mkstemp(dir=os.path.dirname(self.path))
            with os.fdopen(tmpfd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            shutil.move(tmppath, self.path)

    def upsert(self, key: str, value: Any):
        data = self.read()
        data[key] = value
        self.write(data)

    # Added convenience methods for compatibility
    def get(self, key: str, default: Any = None) -> Any:
        return self.read().get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.upsert(key, value)
