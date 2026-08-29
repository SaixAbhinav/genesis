from genesis import load_settings


def test_load_settings():
    s = load_settings("configs/settings.json")
    assert s["minutes_per_day"] == 1440
    assert s["hunger_decay_per_min"] == 0.07
