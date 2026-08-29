import json
from collections import Counter
from pathlib import Path


class DiscoveryGraph:
    def __init__(self, recipes: list[dict], buildables: dict[str, dict]):
        self.recipes = recipes
        self.buildables = buildables

    @classmethod
    def from_file(cls, path: str | Path) -> "DiscoveryGraph":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(d["recipes"], d["buildables"])

    def match(self, items: list[str], knowledge: list[str]) -> str | None:
        have = Counter(items)
        for recipe in self.recipes:
            need = Counter(recipe["items"])
            if all(have[k] >= n for k, n in need.items()) and \
                    all(req in knowledge for req in recipe.get("requires", [])):
                return recipe["result"]
        return None

    def buildable(self, name: str) -> dict | None:
        return self.buildables.get(name)

    def buildable_names(self) -> list[str]:
        return list(self.buildables.keys())
