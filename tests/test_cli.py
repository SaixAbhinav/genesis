from genesis.cli import run_sim
from genesis.persistence.db import connect, load_state


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
