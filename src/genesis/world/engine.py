import json
import random
from pathlib import Path

from genesis.world.actions import step_action
from genesis.world.discovery import DiscoveryGraph
from genesis.world.grid import WorldMap
from genesis.world.hazards import miasma_tick, creature_damage
from genesis.world.instinct import choose_action
from genesis.world.magic import MagicBook
from genesis.world.needs import tick_needs
from genesis.world.state import Resource, WorldState, load_agents
from genesis.world.structures import has_warmth_source


class Engine:
    def __init__(self, state: WorldState, world_map: WorldMap | None = None,
                 settings: dict | None = None, graph: DiscoveryGraph | None = None,
                 maps: list[WorldMap] | None = None,
                 magic: dict | None = None):
        self.state = state
        if maps is None:
            maps = [world_map] if world_map is not None else []
        self.maps = maps
        self.settings = settings
        self.rng = random.Random(state.seed)
        self.graph = graph or DiscoveryGraph.from_file("configs/discoveries.json")
        self.magic = magic

    @classmethod
    def from_configs(cls, config_dir: str | Path = "configs",
                      seed: int = 42, sim_minutes: int = 720) -> "Engine":
        """Build a fully-wired Engine from the on-disk config directory.

        Loads settings.json, layers.json (+ each layer's map/resources file),
        magic.json, agents.json, and discoveries.json; folds the layer list
        into settings["layers"] and relic payloads into settings["relics"]
        (the shapes engine.tick/actions.py already read), and returns a
        ready-to-tick Engine with a fresh WorldState.
        """
        config_dir = Path(config_dir)
        settings = json.loads((config_dir / "settings.json").read_text(encoding="utf-8"))
        layers_cfg = json.loads(
            (config_dir / "layers.json").read_text(encoding="utf-8"))["layers"]

        maps: list[WorldMap] = []
        resources: list[Resource] = []
        relics_payload: dict = {}
        layers_out: list[dict] = []

        for i, layer in enumerate(layers_cfg):
            map_path = config_dir / layer["map"]
            maps.append(WorldMap.from_file(map_path))
            map_data = json.loads(map_path.read_text(encoding="utf-8"))
            for r in map_data.get("resources", []):
                resources.append(Resource(type=r["type"], x=r["x"], y=r["y"],
                                          qty=r["qty"], layer=i))
            for relic in layer.get("relics", []):
                resources.append(Resource(type=relic["type"], x=relic["x"],
                                          y=relic["y"], qty=relic.get("qty", 1),
                                          layer=i))
                payload = {"value": relic.get("value", 0)}
                if "mana_max" in relic:
                    payload["mana_max"] = relic["mana_max"]
                relics_payload[relic["type"]] = payload
            layers_out.append(layer)

        settings["layers"] = layers_out
        settings["relics"] = relics_payload

        state = WorldState(
            sim_minutes=sim_minutes, seed=seed,
            agents=load_agents(config_dir / "agents.json"),
            resources=resources)
        magic = MagicBook.from_file(config_dir / "magic.json")
        graph = DiscoveryGraph.from_file(config_dir / "discoveries.json")
        return cls(state, settings=settings, maps=maps, magic=magic, graph=graph)

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
            layers = self.settings.get("layers", []) if self.settings else []
            if layers and 0 <= agent.layer < len(layers):
                lc = layers[agent.layer]
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
