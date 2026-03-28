import json
import os
import mesa
import cityflow
from agents import Knowledge, ManagerAgent, FixedTimingAgent

class TrafficModel(mesa.Model):
    def __init__(self, config_path="config.json", strategy=None, seed=42):
        super().__init__(seed=seed)
        self.engine = cityflow.Engine(config_path, thread_num=1)
        self.engine.set_random_seed(seed)
        self.strategy = strategy

        knowledge = self._build_knowledge(config_path)
        if strategy:
            self.manager = ManagerAgent(self, knowledge, strategy=strategy)
        else:
            self.manager = FixedTimingAgent(self, knowledge)

        self.datacollector = mesa.DataCollector(
            model_reporters={
                "vehicle_count": lambda m: m.engine.get_vehicle_count(),
                "total_waiting": lambda m: sum(m.engine.get_lane_waiting_vehicle_count().values()),
                "avg_travel_time": lambda m: m.engine.get_average_travel_time(),
            }
        )

    def _build_knowledge(self, config_path):
        with open(config_path) as f:
            cfg = json.load(f)
        roadnet_path = os.path.join(cfg.get("dir", "."), cfg["roadnetFile"])
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
                    up_lanes.add(rl["startRoad"] + "_0")
                    down_lanes.add(rl["endRoad"] + "_0")
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
