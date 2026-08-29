import json
from genesis.world.state import Agent, Resource, WorldState


def test_new_agent_fields_default():
    a = Agent(id="a1", name="Riko", x=0, y=0)
    assert a.layer == 0 and a.strain == 0.0
    assert a.mana == 0.0 and a.mana_max == 0.0
    assert a.attr_rank == {} and a.attr_xp == {}
    assert a.purified_until == 0 and a.negate_fall_until == 0


def test_resource_layer_defaults_zero():
    r = Resource(type="berries", x=1, y=2, qty=3)
    assert r.layer == 0


def test_roundtrip_preserves_abyss_fields():
    a = Agent(id="a1", name="Riko", x=0, y=0, layer=2, strain=12.5,
              mana=30.0, mana_max=50.0, attr_rank={"healing": 1},
              attr_xp={"healing": 25.0}, status="dead")
    ws = WorldState(sim_minutes=0, seed=1, agents=[a],
                    resources=[Resource("relic", 3, 3, 1, layer=2)])
    back = WorldState.from_json(ws.to_json())
    b = back.agents[0]
    assert b.layer == 2 and b.strain == 12.5 and b.status == "dead"
    assert b.attr_rank == {"healing": 1} and b.mana_max == 50.0
    assert back.resources[0].layer == 2


def test_from_json_loads_pre_plan3_agent():
    # Old JSON with no abyss/magic keys must still load.
    old = json.dumps({"sim_minutes": 0, "seed": 1,
                      "agents": [{"id": "a1", "name": "R", "x": 0, "y": 0,
                                  "needs": {"hunger": 100.0, "energy": 100.0,
                                            "warmth": 100.0}, "inventory": {},
                                  "status": "active", "persona": "", "brain": "",
                                  "knowledge": [], "current_action": None,
                                  "collapse_until": 0}],
                      "resources": [{"type": "berries", "x": 1, "y": 1, "qty": 2}],
                      "structures": []})
    ws = WorldState.from_json(old)
    assert ws.agents[0].layer == 0 and ws.agents[0].mana_max == 0.0
    assert ws.resources[0].layer == 0
