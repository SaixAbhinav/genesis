from genesis import load_settings
from genesis.world.state import Agent, WorldState
from genesis.world.grid import WorldMap
from genesis.world.discovery import DiscoveryGraph
from genesis.world.actions import validate_action, step_action

S = load_settings("configs/settings.json")
M = WorldMap.from_file("configs/map.json")
G = DiscoveryGraph.from_file("configs/discoveries.json")


def world(agent):
    return WorldState(sim_minutes=7, seed=1, agents=[agent])


def test_build_campfire_places_structure_and_consumes_wood():
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["fire"],
              inventory={"wood": 3},
              current_action={"action": "build", "structure": "campfire"})
    st = world(a)
    ev = step_action(a, st, M, S, G)
    assert ev[0]["type"] == "built" and ev[0]["structure"] == "campfire"
    assert a.inventory["wood"] == 1                       # 3 - 2
    assert st.structures[0].type == "campfire"
    assert (st.structures[0].x, st.structures[0].y) == (5, 5)
    assert st.structures[0].built_by == "a"


def test_build_torch_goes_to_inventory_not_map():
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["fire"],
              inventory={"wood": 1},
              current_action={"action": "build", "structure": "torch"})
    st = world(a)
    ev = step_action(a, st, M, S, G)
    assert ev[0]["type"] == "built"
    assert a.inventory.get("torch") == 1 and st.structures == []


def test_build_rejected_without_knowledge():
    a = Agent(id="a", name="A", x=5, y=5, inventory={"wood": 3})
    ok, why = validate_action(
        {"action": "build", "structure": "campfire"}, a, world(a), M, G)
    assert ok is False and "fire" in why


def test_build_failed_without_materials():
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["fire"], inventory={"wood": 1},
              current_action={"action": "build", "structure": "campfire"})
    ev = step_action(a, world(a), M, S, G)
    assert ev[0]["type"] == "build_failed"


def test_build_failed_on_wrong_terrain():
    # (12,0) is cave terrain, which is not in campfire's allowed terrain list.
    a = Agent(id="a", name="A", x=12, y=0, knowledge=["fire"], inventory={"wood": 3},
              current_action={"action": "build", "structure": "campfire"})
    ev = step_action(a, world(a), M, S, G)
    assert ev[0]["type"] == "build_failed"


def test_build_failed_when_tile_occupied():
    from genesis.world.structures import Structure
    a = Agent(id="a", name="A", x=5, y=5, knowledge=["fire"], inventory={"wood": 3},
              current_action={"action": "build", "structure": "campfire"})
    st = world(a)
    st.structures.append(Structure(type="campfire", x=5, y=5,
                                   built_by="b", built_minute=1))
    ev = step_action(a, st, M, S, G)
    assert ev[0]["type"] == "build_failed"
