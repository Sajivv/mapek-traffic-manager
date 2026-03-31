import json
import os

import cityflow
import mesa

from agents import FixedTimingAgent, Knowledge, ManagerAgent


class TrafficModel(mesa.Model):
    def __init__(self, config_path="config.json", strategy=None, seed=42):
        super().__init__(seed=seed)
        self.config_path = os.path.abspath(config_path)
        self.engine = cityflow.Engine(self.config_path, thread_num=1)
        self.engine.set_random_seed(seed)
        self.strategy = strategy

        knowledge = self._build_knowledge()

        if strategy in ("pressure", "adaptive"):
            self.manager = ManagerAgent(self, knowledge, strategy=strategy)
        elif strategy is None:
            self.manager = FixedTimingAgent(self, knowledge)
        else:
            raise ValueError(
                f"Unknown strategy: {strategy!r}. Use 'pressure', 'adaptive', or None."
            )

        self.datacollector = mesa.DataCollector(
            model_reporters={
                "vehicle_count": lambda m: m.engine.get_vehicle_count(),
                "total_waiting": lambda m: sum(
                    m.engine.get_lane_waiting_vehicle_count().values()
                ),
                "avg_travel_time": lambda m: m.engine.get_average_travel_time(),
                "network_pressure": lambda m: getattr(m.manager, "last_total_pressure", 0.0),
                "total_switches": lambda m: getattr(m.manager, "last_total_switches", 0),
                "active_upstream_waiting": lambda m: getattr(
                    m.manager, "last_active_upstream_waiting", 0.0
                ),
                "active_downstream_waiting": lambda m: getattr(
                    m.manager, "last_active_downstream_waiting", 0.0
                ),
                "active_score": lambda m: getattr(m.manager, "last_active_score", 0.0),
                "pressure_weight": lambda m: getattr(
                    m.manager.knowledge, "pressure_weight", 0.0
                ),
                "downstream_weight": lambda m: getattr(
                    m.manager.knowledge, "downstream_weight", 0.0
                ),
                "switch_weight": lambda m: getattr(
                    m.manager.knowledge, "switch_weight", 0.0
                ),
            }
        )

    def _build_knowledge(self):
        with open(self.config_path) as f:
            cfg = json.load(f)
        config_dir = os.path.dirname(self.config_path)
        roadnet_path = os.path.join(config_dir, cfg.get("dir", "."), cfg["roadnetFile"])
        with open(roadnet_path) as f:
            net = json.load(f)

        intersection_ids = []
        phase_lanes = {}
        downstream_lanes = {}
        current_phase = {}
        phase_timer = {}

        for inter in net["intersections"]:
            iid = inter["id"]
            tl = inter.get("trafficLight")
            if not tl or not tl.get("lightphases"):
                continue

            intersection_ids.append(iid)
            road_links = inter["roadLinks"]
            phase_lanes[iid] = {}
            downstream_lanes[iid] = {}

            for pidx, phase in enumerate(tl["lightphases"]):
                up_lanes = set()
                down_lanes = set()
                for rli in phase["availableRoadLinks"]:
                    rl = road_links[rli]
                    for ll in rl["laneLinks"]:
                        up_lanes.add(f"{rl['startRoad']}_{ll['startLaneIndex']}")
                        down_lanes.add(f"{rl['endRoad']}_{ll['endLaneIndex']}")
                phase_lanes[iid][pidx] = list(up_lanes)
                downstream_lanes[iid][pidx] = list(down_lanes)

            current_phase[iid] = 0
            phase_timer[iid] = 0

        return Knowledge(
            intersection_ids=intersection_ids,
            phase_lanes=phase_lanes,
            downstream_lanes=downstream_lanes,
            current_phase=current_phase,
            phase_timer=phase_timer,
        )

    def step(self):
        self.manager.step()
        self.engine.next_step()
        self.datacollector.collect(self)
