import json
import random
from pathlib import Path

from genesis.mind.brain import InstinctBrain
from genesis.mind.queue import DecisionJob
from genesis.world.actions import step_action
from genesis.world.affordances import affordances
from genesis.world.discovery import DiscoveryGraph
from genesis.world.goal import resolve_goal
from genesis.world.grid import WorldMap
from genesis.world.hazards import miasma_tick, creature_damage
from genesis.world.magic import MagicBook
from genesis.world.needs import tick_needs
from genesis.world.state import Resource, WorldState, load_agents
from genesis.world.structures import has_warmth_source


class Engine:
    def __init__(self, state: WorldState, world_map: WorldMap | None = None,
                 settings: dict | None = None, graph: DiscoveryGraph | None = None,
                 maps: list[WorldMap] | None = None,
                 magic: dict | None = None, brains: dict | None = None,
                 queue=None):
        self.state = state
        if maps is None:
            maps = [world_map] if world_map is not None else []
        self.maps = maps
        self.settings = settings
        self.rng = random.Random(state.seed)
        self.graph = graph or DiscoveryGraph.from_file("configs/discoveries.json")
        self.magic = magic
        self.brains = brains or {}
        self.queue = queue
        self.instinct = InstinctBrain()
        self._last_submit: dict[str, int] = {}
        self._live = True

    @classmethod
    def from_configs(cls, config_dir: str | Path = "configs",
                      seed: int = 42, sim_minutes: int = 720,
                      minds: bool = False) -> "Engine":
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

        brains, queue = {}, None
        if minds:
            from genesis.mind.groq import GroqAdapter
            from genesis.mind.llm_brain import LLMBrain
            from genesis.mind.queue import ThreadedThinkQueue
            cfg = json.loads(
                (config_dir / "brains.json").read_text(encoding="utf-8"))["brains"]
            for ag in state.agents:
                spec = cfg.get(ag.brain) or cfg["default"]
                brains[ag.id] = LLMBrain(GroqAdapter(spec["model"]), spec["model"])
            queue = ThreadedThinkQueue(settings.get("daily_request_budget", 900))

        return cls(state, settings=settings, maps=maps, magic=magic, graph=graph,
                   brains=brains, queue=queue)

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
                action, extra = self._decide(agent, wm)
                agent.current_action = action
                events += extra
            events += step_action(agent, self.state, wm,
                                  self.settings, self.graph, self.magic, self.rng)
        for ev in events:
            ev.setdefault("minute", minute)
        self.state.sim_minutes += 1
        return events

    def advance(self, minutes: int, live: bool = True) -> list[dict]:
        self._live = live
        events: list[dict] = []
        for _ in range(minutes):
            events += self.tick()
        return events

    def _decide(self, agent, wm):
        minute = self.state.sim_minutes
        extra: list[dict] = []
        # 1. drive an active goal
        if agent.goal is not None:
            act = self._drive(agent, wm)
            if act is not None:
                return act, extra
        # 2/3. LLM path (only if a brain+queue are wired for this agent, and
        # only during live simulation — ADR 0001: catch-up/fast-forward runs
        # Instinct-only and must never submit LLM jobs).
        brain = self.brains.get(agent.id)
        if self._live and self.queue is not None and brain is not None:
            menu = affordances(agent, self.state, wm, self.settings,
                               self.graph, self.magic)
            landed = self._consume(agent, wm, menu, minute, extra)
            if landed is not None:
                return landed, extra
            cooldown = self.settings.get("decision_cooldown_min", 0)
            if (not self.queue.pending(agent.id)
                    and minute - self._last_submit.get(agent.id, -10**9) >= cooldown
                    and menu):
                ctx = self._context(agent, menu)
                self.queue.submit(DecisionJob(agent.id, minute, menu, ctx), brain)
                self._last_submit[agent.id] = minute
                landed = self._consume(agent, wm, menu, minute, extra)  # InlineQueue: ready now
                if landed is not None:
                    return landed, extra
        # 4. instinct meanwhile / fallback
        return self.instinct.act(agent, self.state, wm, self.settings,
                                 self.rng, self.graph, self.magic), extra

    def _drive(self, agent, wm):
        goal = agent.goal
        act = resolve_goal(agent, goal, self.state, wm, self.settings,
                           self.graph, self.magic)
        if act is None:
            agent.goal = None
            return None
        # A relocation move_to (verb != goal verb) keeps the goal alive so the
        # engine walks the whole path. Once the terminal verb action is issued
        # (act verb == goal verb), clear the goal so the agent re-decides next
        # time instead of re-issuing the same one-shot action every tick.
        if act.get("action") == goal.get("verb"):
            agent.goal = None
        return act

    def _consume(self, agent, wm, menu, minute, extra):
        d = self.queue.pop(agent.id)
        if d is None:
            return None
        aff = next((o for o in menu if o["id"] == d["choice"]), None)
        stale = self.settings.get("decision_stale_min", 10**9)
        if aff is None or minute - d["sim_minute"] > stale:
            return None  # stale/invalid -> drop, re-decide later
        agent.goal = aff
        model = getattr(self.brains.get(agent.id), "model", "fake")
        extra.append({"type": "decided", "agent": agent.id, "choice": aff["id"],
                      "reason": d["reason"], "model": model, "minute": minute})
        return self._drive(agent, wm)

    def _context(self, agent, menu):
        return {"persona": agent.persona, "needs": vars(agent.needs),
                "strain": agent.strain, "mana": agent.mana, "mana_max": agent.mana_max,
                "layer": agent.layer, "inventory": dict(agent.inventory),
                "known": list(agent.knowledge), "options": menu}
