from genesis.world.actions import step_action, validate_action
from genesis.world.grid import WorldMap
from genesis.world.magic import MagicBook
from genesis.world.state import Agent, WorldState

WM = WorldMap(["GG", "GG"])
SET = {"campfire_warmth_radius": 1}
BOOK = MagicBook.from_dict({
    "attributes": ["healing"], "ranks": ["beginner", "intermediate"],
    "rank_xp": {"beginner": 0, "intermediate": 20},
    "spells": [{"name": "minor_heal", "kind": "spell", "attribute": "healing",
                "requires": [], "prereqs": {"attribute_rank": {"healing": "beginner"}},
                "base_cast_minutes": 2, "mana_cost": 10, "xp_per_cast": 6,
                "effect": {"type": "reduce_strain", "amount": 20}}],
    "params": {"mana_depletion_frac": 0.15, "mana_growth_step": 5.0}})


def _mage():
    return Agent(id="m", name="M", x=0, y=0, mana=30.0, mana_max=40.0,
                 strain=30.0, knowledge=["minor_heal"],
                 attr_rank={"healing": 0}, attr_xp={"healing": 0.0})


def test_cast_rejected_when_spell_unknown():
    a = _mage(); a.knowledge = []
    ok, why = validate_action({"action": "cast", "spell": "minor_heal"},
                              a, WorldState(0, 1, [a]), WM, magic=BOOK)
    assert not ok and "know" in why


def test_cast_rejected_when_insufficient_mana():
    a = _mage(); a.mana = 3.0
    ok, why = validate_action({"action": "cast", "spell": "minor_heal"},
                              a, WorldState(0, 1, [a]), WM, magic=BOOK)
    assert not ok and "mana" in why


def test_cast_completes_after_chant_and_applies_effect():
    a = _mage()
    st = WorldState(0, 1, [a])
    a.current_action = {"action": "cast", "spell": "minor_heal"}
    # First tick: chanting (2 minutes) -> no completion yet
    st.sim_minutes = 0
    ev = step_action(a, st, WM, SET, None, BOOK)
    assert a.current_action is not None  # still chanting
    # Advance to completion minute
    st.sim_minutes = 2
    ev = step_action(a, st, WM, SET, None, BOOK)
    assert a.strain == 10.0            # reduced by 20
    assert a.mana == 20.0              # 30 - 10
    assert a.attr_xp["healing"] == 6.0
    assert a.current_action is None
    assert any(e["type"] == "cast" for e in ev)
