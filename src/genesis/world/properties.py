import json
from pathlib import Path


class PropertyBook:
    def __init__(self, materials: dict[str, list[str]]):
        self._props = {k: frozenset(v) for k, v in materials.items()}

    @classmethod
    def from_file(cls, path: str | Path) -> "PropertyBook":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(d.get("materials", {}))

    def props_of(self, name: str) -> frozenset:
        return self._props.get(name, frozenset())
