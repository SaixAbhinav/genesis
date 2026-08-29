import pytest
from genesis.world.grid import WorldMap


def test_map_loads_and_terrain():
    m = WorldMap.from_file("configs/map.json")
    assert (m.width, m.height) == (20, 15)
    assert m.terrain(0, 0) == "forest"
    assert m.terrain(12, 0) == "cave"
    assert m.terrain(5, 8) == "water"
    assert m.terrain(14, 9) == "marsh"


def test_walkable_and_bounds():
    m = WorldMap.from_file("configs/map.json")
    assert m.walkable(0, 0) is True
    assert m.walkable(5, 8) is False          # water
    assert m.walkable(-1, 0) is False
    with pytest.raises(ValueError):
        m.terrain(99, 99)


def test_neighbors4():
    m = WorldMap.from_file("configs/map.json")
    assert set(m.neighbors4(0, 0)) == {(1, 0), (0, 1)}
    assert len(m.neighbors4(5, 5)) == 4
