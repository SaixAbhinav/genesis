from genesis import load_settings
from genesis.world.state import Needs, Agent, Resource, WorldState, load_agents


def test_load_settings():
    s = load_settings("configs/settings.json")
    assert s["minutes_per_day"] == 1440
    assert s["hunger_decay_per_min"] == 0.07


def test_world_state_json_roundtrip():
    a = Agent(id="ash", name="Ash", x=1, y=2, needs=Needs(hunger=50.0))
    ws = WorldState(sim_minutes=10, seed=42, agents=[a],
                    resources=[Resource(type="berries", x=3, y=4, qty=9)])
    ws2 = WorldState.from_json(ws.to_json())
    assert ws2.agents[0].needs.hunger == 50.0
    assert ws2.agents[0].needs.energy == 100.0
    assert ws2.resources[0].qty == 9
    assert ws2.seed == 42


def test_load_agents():
    agents = load_agents("configs/agents.json")
    assert len(agents) == 4
    assert agents[0].name == "Ash"
    assert agents[0].status == "active"


def test_agent_goal_round_trips_through_json():
    from genesis.world.state import Agent, WorldState
    a = Agent(id="a", name="A", x=0, y=0, goal={"id": "eat", "verb": "eat"})
    st = WorldState(sim_minutes=0, seed=1, agents=[a])
    back = WorldState.from_json(st.to_json())
    assert back.agents[0].goal == {"id": "eat", "verb": "eat"}
