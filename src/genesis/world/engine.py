import random

from genesis.world.actions import step_action
from genesis.world.discovery import DiscoveryGraph
from genesis.world.grid import WorldMap
from genesis.world.hazards import miasma_tick, creature_damage
from genesis.world.instinct import choose_action
from genesis.world.needs import tick_needs
from genesis.world.state import WorldState
from genesis.world.structures import has_warmth_source


class Engine:
    def __init__(self, state: WorldState, world_map: WorldMap | None = None,
                 settings: dict | None = None, graph: DiscoveryGraph | None = None,
                 maps: list[WorldMap] | None = None, layers: list | None = None,
                 magic: dict | None = None):
        self.state = state
        if maps is None:
            maps = [world_map] if world_map is not None else []
        self.maps = maps
        self.settings = settings
        self.rng = random.Random(state.seed)
        self.graph = graph or DiscoveryGraph.from_file("configs/discoveries.json")
        self.layers = layers or []
        self.magic = magic

    def map_for(self, agent):
        return self.maps[agent.layer]

    def tick(self) -> list[dict]:
        events: list[dict] = []
        minute = self.state.sim_minutes
        for agent in self.state.agents:
            if agent.status == "dead":
                continue
            wm = self.map_for(agent)
            near = has_warmth_source(agent, self.state, self.settings)
            events += tick_needs(agent, minute, self.settings, near_warmth=near)
            if self.layers and 0 <= agent.layer < len(self.layers):
                lc = self.layers[agent.layer]
                events += miasma_tick(agent, lc, minute)
                events += creature_damage(agent, lc)
            if agent.current_action is None and agent.status in ("active", "sleeping"):
                agent.current_action = choose_action(
                    agent, self.state, wm, self.settings, self.rng,
                    self.graph, self.magic)
            events += step_action(agent, self.state, wm,
                                  self.settings, self.graph, self.magic, self.rng)
        for ev in events:
            ev.setdefault("minute", minute)
        self.state.sim_minutes += 1
        return events

    def advance(self, minutes: int) -> list[dict]:
        events: list[dict] = []
        for _ in range(minutes):
            events += self.tick()
        return events
