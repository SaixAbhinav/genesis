from genesis.cli import run_sim
from genesis.persistence.db import connect, load_state


def test_engine_loads_three_layer_world():
    from genesis.world.engine import Engine
    from genesis.world.grid import WorldMap
    import json, pathlib
    cfg = pathlib.Path("configs")
    layers = json.loads((cfg / "layers.json").read_text())
    assert len(layers["layers"]) == 3
    maps = [WorldMap.from_file(cfg / l["map"]) for l in layers["layers"]]
    assert len(maps) == 3
    engine = Engine.from_configs("configs")
    assert len(engine.maps) == 3
    assert len(engine.settings["layers"]) == 3
    assert engine.magic is not None


def test_run_sim_two_days_survives_and_persists(tmp_path):
    db = tmp_path / "w.db"
    summary = run_sim(days=2, db_path=db, seed=42)
    assert summary["sim_minutes"] == 720 + 2 * 1440
    assert summary["event_counts"].get("moved", 0) > 0
    assert len(summary["agents"]) == 4
    # persisted: a second run continues from saved time
    summary2 = run_sim(days=0.5, db_path=db, seed=42)
    assert summary2["sim_minutes"] == 720 + 2 * 1440 + 720


def test_agents_do_not_stay_collapsed_forever(tmp_path):
    summary = run_sim(days=3, db_path=tmp_path / "w.db", seed=7)
    collapsed_final = [a for a in summary["agents"] if a["status"] == "collapsed"]
    assert len(collapsed_final) < 4     # world did not dead-end


def test_discoveries_and_structures_emerge(tmp_path):
    summary = run_sim(days=2, db_path=tmp_path / "w.db", seed=42)
    # someone should have discovered fire and stone_tools from seeded materials
    all_known = {d for known in summary["discoveries"].values() for d in known}
    assert "fire" in all_known
    assert "stone_tools" in all_known
    # and at least one structure should have been built
    assert len(summary["structures"]) >= 1
    assert summary["structures"][0]["type"] in ("campfire", "hut")
