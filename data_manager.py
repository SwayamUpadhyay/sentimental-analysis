
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_BASE = Path(__file__).parent
_DATA_FILE = _BASE / "Data.json"
_MEMORY_FILE = _BASE / "memory.json"



def _read(path: Path, default: Any) -> Any:
    if not path.exists():
        _write(path, default)
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        _write(path, default)
        return default


def _write(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)



class DataStore:

    _DEFAULT: dict = {"sessions": []}

    def append_session(self, session: dict) -> None:
        data = _read(_DATA_FILE, self._DEFAULT)
        data["sessions"].append(session)
        _write(_DATA_FILE, data)
        print(f"[DataStore] Session appended for '{session.get('product', '?')}'. "
              f"Total sessions: {len(data['sessions'])}")

    def get_all_sessions(self) -> list:
        return _read(_DATA_FILE, self._DEFAULT).get("sessions", [])

    def get_latest(self) -> dict | None:
        sessions = self.get_all_sessions()
        return sessions[-1] if sessions else None

    def get_by_product(self, product_name: str) -> list:
        return [
            s for s in self.get_all_sessions()
            if s.get("product", "").lower() == product_name.lower()
        ]

    def count(self) -> int:
        return len(self.get_all_sessions())

    def clear(self) -> None:
        _write(_DATA_FILE, self._DEFAULT)
        print("[DataStore] Cleared — all session history deleted.")



class MemoryStore:

    _DEFAULT: dict = {"contexts": []}

    def append_context(self, context: dict) -> None:
        data = _read(_MEMORY_FILE, self._DEFAULT)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **context,
        }
        data["contexts"].append(entry)
        _write(_MEMORY_FILE, data)
        print(f"[MemoryStore] Context logged for '{context.get('product', '?')}'.")

    def get_history(self, n: int = 10) -> list:
        contexts = _read(_MEMORY_FILE, self._DEFAULT).get("contexts", [])
        return contexts[-n:]

    def get_all(self) -> list:
        return _read(_MEMORY_FILE, self._DEFAULT).get("contexts", [])

    def count(self) -> int:
        return len(self.get_all())

    def clear(self) -> None:
        _write(_MEMORY_FILE, self._DEFAULT)
        print("[MemoryStore] Cleared — all context history deleted.")
