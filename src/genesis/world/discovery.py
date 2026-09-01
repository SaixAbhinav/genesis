import json
from collections import Counter
from pathlib import Path


def covering_subset(have, required, props_of):
    remaining = set(required)
    used = []
    for item in sorted(have):
        contrib = props_of(item) & remaining
        if contrib:
            used.append(item)
            remaining -= contrib
    return used if not remaining else None


class DiscoveryGraph:
    def __init__(self, recipes: list[dict], buildables: dict[str, dict], props=None):
        self.recipes = recipes
        self.buildables = buildables
        self.props = props

    @classmethod
    def from_file(cls, path: str | Path, props=None) -> "DiscoveryGraph":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(d["recipes"], d["buildables"], props)

    def _prereqs_met(self, recipe: dict, agent) -> bool:
        for tech in recipe.get("prereqs", {}).get("knowledge", []):
            if tech not in agent.knowledge:
                return False
        return True

    def resolve(self, items: list[str], agent):
        if self.props is None:
            return None, None
        have = {it for it in items if agent.inventory.get(it, 0) > 0}
        for recipe in self.recipes:
            if recipe.get("kind", "knowledge") != "item" \
                    and recipe["name"] in agent.knowledge:
                continue
            if not self._prereqs_met(recipe, agent):
                continue
            cover = covering_subset(have, recipe.get("requires", []),
                                    self.props.props_of)
            if cover is None or len(cover) < recipe.get("min_items", 1):
                continue
            return recipe, cover
        return None, None

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
