from genesis.world.state import Agent, WorldState
from genesis.persistence.db import connect, save_state, load_state, append_events, load_events


def test_state_roundtrip(tmp_path):
    conn = connect(tmp_path / "w.db")
    assert load_state(conn) is None
    ws = WorldState(sim_minutes=99, seed=5,
                    agents=[Agent(id="a", name="A", x=1, y=1)])
    save_state(conn, ws)
    ws.sim_minutes = 150
    save_state(conn, ws)                     # upsert, not duplicate
    loaded = load_state(conn)
    assert loaded.sim_minutes == 150 and loaded.agents[0].name == "A"


def test_event_log_appends_and_filters(tmp_path):
    conn = connect(tmp_path / "w.db")
    append_events(conn, [{"type": "moved", "minute": 10, "agent": "a"},
                         {"type": "ate", "minute": 20, "agent": "a"}])
    assert len(load_events(conn)) == 2
    later = load_events(conn, since_minute=15)
    assert len(later) == 1 and later[0]["type"] == "ate"
