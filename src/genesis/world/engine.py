import random

from genesis.world.actions import step_action
from genesis.world.grid import WorldMap
from genesis.world.instinct import choose_action
from genesis.world.needs import tick_needs
from genesis.world.state import WorldState
from genesis.world.structures import has_warmth_source


class Engine:
    def __init__(self, state: WorldState, world_map: WorldMap, settings: dict):
        self.state = state
        self.world_map = world_map
        self.settings = settings
        self.rng = random.Random(state.seed)

    def tick(self) -> list[dict]:
        events: list[dict] = []
        minute = self.state.sim_minutes
        for agent in self.state.agents:
            near = has_warmth_source(agent, self.state, self.settings)
            events += tick_needs(agent, minute, self.settings, near_warmth=near)
            if agent.current_action is None and agent.status in ("active", "sleeping"):
                agent.current_action = choose_action(
                    agent, self.state, self.world_map, self.settings, self.rng)
            events += step_action(agent, self.state, self.world_map, self.settings)
        for ev in events:
            ev.setdefault("minute", minute)
        self.state.sim_minutes += 1
        return events

    def advance(self, minutes: int) -> list[dict]:
        events: list[dict] = []
        for _ in range(minutes):
            events += self.tick()
        return events
