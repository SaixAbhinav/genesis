from genesis import load_settings
from genesis.world.state import Agent, Needs, Resource, WorldState
from genesis.world.grid import WorldMap
from genesis.world.actions import step_action

S = load_settings("configs/settings.json")
M = WorldMap.from_file("configs/map.json")


def test_stone_tools_double_gather_yield():
    r = Resource(type="wood", x=5, y=5, qty=10)
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["stone_tools"],
              current_action={"action": "gather", "resource": "wood"})
    st = WorldState(sim_minutes=0, seed=1, agents=[a], resources=[r])
    step_action(a, st, M, S)
    assert a.inventory["wood"] == 1 + S["stone_tools_gather_bonus"]
    assert r.qty == 10 - (1 + S["stone_tools_gather_bonus"])


def test_gather_yield_capped_at_remaining_qty():
    r = Resource(type="wood", x=5, y=5, qty=1)
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["stone_tools"],
              current_action={"action": "gather", "resource": "wood"})
    st = WorldState(sim_minutes=0, seed=1, agents=[a], resources=[r])
    step_action(a, st, M, S)
    assert a.inventory["wood"] == 1 and r.qty == 0


def test_cooked_food_restores_more_hunger():
    a = Agent(id="a", name="A", x=5, y=5, needs=Needs(hunger=10.0),
              knowledge=["cooked_food"], inventory={"berries": 1},
              current_action={"action": "eat"})
    st = WorldState(sim_minutes=0, seed=1, agents=[a])
    step_action(a, st, M, S)
    assert a.needs.hunger == 10 + S["eat_berries_hunger_restore"] + S["eat_cooked_hunger_bonus"]
