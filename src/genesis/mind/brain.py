from genesis.world.instinct import choose_action


class BrainError(Exception):
    pass


class InstinctBrain:
    """The deterministic reflex Mind — today's choose_action, unchanged."""
    def act(self, agent, state, world_map, settings, rng, graph=None, magic=None):
        return choose_action(agent, state, world_map, settings, rng, graph, magic)


class FakeBrain:
    """Scripted LLM Brain for deterministic tests. `chooser(ctx, affs)->dict`."""
    def __init__(self, chooser):
        self._chooser = chooser

    def choose(self, context: dict, affordances: list[dict]) -> dict:
        return self._chooser(context, affordances)
