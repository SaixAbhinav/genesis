import json
from pathlib import Path

TERRAIN = {"G": "grass", "F": "forest", "R": "rock", "W": "water",
           "S": "sand", "C": "cave", "M": "marsh"}


class WorldMap:
    def __init__(self, rows: list[str]):
        self.rows = rows
        self.height = len(rows)
        self.width = len(rows[0])

    @classmethod
    def from_file(cls, path: str | Path) -> "WorldMap":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(d["rows"])

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def terrain(self, x: int, y: int) -> str:
        if not self.in_bounds(x, y):
            raise ValueError(f"out of bounds: ({x}, {y})")
        return TERRAIN[self.rows[y][x]]

    def walkable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and self.terrain(x, y) != "water"

    def neighbors4(self, x: int, y: int) -> list[tuple[int, int]]:
        cand = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [(cx, cy) for cx, cy in cand if self.in_bounds(cx, cy)]
