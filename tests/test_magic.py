from genesis.world.magic import MagicBook
from genesis.world.state import Agent

BOOK = MagicBook.from_dict({
    "attributes": ["fire", "water", "wind", "earth", "healing"],
    "ranks": ["beginner", "intermediate", "advanced", "saint", "king"],
    "rank_xp": {"beginner": 0, "intermediate": 20, "advanced": 60,
                "saint": 140, "king": 300},
    "spells": [
        {"name": "minor_heal", "kind": "spell", "attribute": "healing",
         "requires": [], "prereqs": {"attribute_rank": {"healing": "beginner"}},
         "base_cast_minutes": 4, "mana_cost": 10, "xp_per_cast": 6,
         "effect": {"type": "reduce_strain", "amount": 20}},
    ],
    "params": {"mana_depletion_frac": 0.15, "mana_growth_step": 5.0},
})


def _mage(**kw):
    return Agent(id="m", name="M", x=0, y=0, **kw)


def test_spell_lookup():
    assert BOOK.spell("minor_heal")["attribute"] == "healing"
    assert BOOK.spell("nope") is None


def test_cast_minutes_shrinks_with_rank():
    beginner = _mage(attr_rank={"healing": 0})
    advanced = _mage(attr_rank={"healing": 2})
    sp = BOOK.spell("minor_heal")
    assert BOOK.cast_minutes(sp, beginner) == 4
    assert BOOK.cast_minutes(sp, advanced) == 2  # 4 - rank_index, min 1


def test_award_xp_ranks_up_at_threshold():
    a = _mage(attr_rank={"healing": 0}, attr_xp={"healing": 18.0})
    ranked = BOOK.award_xp(a, "healing", amount=6)  # 24 >= 20 -> intermediate
    assert ranked is True and a.attr_rank["healing"] == 1


def test_award_xp_no_rankup_below_threshold():
    a = _mage(attr_rank={"healing": 0}, attr_xp={"healing": 5.0})
    assert BOOK.award_xp(a, "healing", amount=6) is False
    assert a.attr_rank["healing"] == 0


def test_mana_pool_grows_when_depleted():
    a = _mage(mana=1.0, mana_max=50.0)  # 1/50 = 0.02 < 0.15
    BOOK.note_cast_mana(a)
    assert a.mana_max == 55.0


def test_mana_pool_stable_when_not_depleted():
    a = _mage(mana=40.0, mana_max=50.0)
    BOOK.note_cast_mana(a)
    assert a.mana_max == 50.0
