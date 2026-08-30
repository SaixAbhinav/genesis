from genesis.mind.brain import InstinctBrain, FakeBrain
from genesis.world.grid import WorldMap
from genesis.world.state import Agent, WorldState
import random

WM = WorldMap(["GG", "GG"])


def test_instinct_brain_matches_choose_action():
    from genesis.world.instinct import choose_action
    a = Agent(id="a", name="A", x=0, y=0)
    st = WorldState(0, 7, [a])
    S = {"minutes_per_day": 1000, "day_start_minute": 0, "day_end_minute": 1000}
    expected = choose_action(a, st, WM, S, random.Random(7))
    got = InstinctBrain().act(a, st, WM, S, random.Random(7))
    assert got == expected


def test_fake_brain_returns_scripted_choice():
    fb = FakeBrain(lambda ctx, affs: {"choice": affs[0]["id"], "reason": "first"})
    out = fb.choose({}, [{"id": "eat"}, {"id": "sleep"}])
    assert out == {"choice": "eat", "reason": "first"}
