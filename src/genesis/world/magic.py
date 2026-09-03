import json
from pathlib import Path

from genesis.world.discovery import covering_subset


class MagicBook:
    def __init__(self, attributes, ranks, rank_xp, spells, params, props=None):
        self.attributes = attributes
        self.ranks = ranks
        self.rank_xp = rank_xp
        self.spells = {s["name"]: s for s in spells}
        self.params = params
        self.props = props

    @classmethod
    def from_dict(cls, d, props=None):
        return cls(d["attributes"], d["ranks"], d["rank_xp"],
                   d["spells"], d.get("params", {}), props)

    @classmethod
    def from_file(cls, path, props=None):
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")), props)

    def resolve(self, items, agent):
        if self.props is None:
            return None, None
        have = {it for it in items if agent.inventory.get(it, 0) > 0}
        for name, spell in self.spells.items():
            if name in agent.knowledge:
                continue
            req = spell.get("requires", [])
            if not req:
                continue
            cover = covering_subset(have, req, self.props.props_of)
            if cover is None or len(cover) < spell.get("min_items", 1):
                continue
            return spell, cover
        return None, None

    def spell(self, name):
        return self.spells.get(name)

    def cast_minutes(self, spell, agent):
        rank = agent.attr_rank.get(spell["attribute"], 0)
        return max(1, int(spell["base_cast_minutes"]) - rank)

    def award_xp(self, agent, attribute, amount):
        agent.attr_xp[attribute] = agent.attr_xp.get(attribute, 0.0) + float(amount)
        rank = agent.attr_rank.get(attribute, 0)
        # rank up while the next rank's threshold is met and one exists
        while rank + 1 < len(self.ranks):
            nxt = self.ranks[rank + 1]
            if agent.attr_xp[attribute] >= self.rank_xp[nxt]:
                rank += 1
            else:
                break
        ranked_up = rank != agent.attr_rank.get(attribute, 0)
        agent.attr_rank[attribute] = rank
        return ranked_up

    def note_cast_mana(self, agent):
        frac = self.params.get("mana_depletion_frac", 0.15)
        step = self.params.get("mana_growth_step", 5.0)
        if agent.mana_max > 0 and agent.mana <= frac * agent.mana_max:
            agent.mana_max += step
