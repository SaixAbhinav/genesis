from genesis.world.properties import PropertyBook

B = PropertyBook.from_file("configs/properties.json")


def test_props_of_known_material():
    assert B.props_of("flint") == frozenset({"sharp", "sparks"})
    assert "flammable" in B.props_of("wood")


def test_props_of_unknown_is_empty():
    assert B.props_of("nonsense") == frozenset()


def test_produced_items_carry_properties():
    assert "hot_burning" in B.props_of("charcoal")
    assert "metallic" in B.props_of("metal_ingot")
