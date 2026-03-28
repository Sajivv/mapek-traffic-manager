from dataclasses import dataclass, field

import mesa


@dataclass
class Knowledge:
    min_green: int = 10
    max_green: int = 60
    intersection_ids: list = field(default_factory=list)
    phase_lanes: dict = field(default_factory=dict)
    downstream_lanes: dict = field(default_factory=dict)
    current_phase: dict = field(default_factory=dict)
    phase_timer: dict = field(default_factory=dict)


class ManagerAgent(mesa.Agent):
    def __init__(self, model, knowledge, strategy="pressure"):
        super().__init__(model)
        self.knowledge = knowledge
        self.strategy = strategy
        self.observed = {}
        self.needs_switch = {}
        self.planned_phases = {}

    def step(self):
        self.monitor()
        self.analyze()
        self.plan()
        self.execute()

    def monitor(self):
        eng = self.model.engine
        self.observed = {
            "lane_vehicles": eng.get_lane_vehicle_count(),
            "lane_waiting": eng.get_lane_waiting_vehicle_count(),
            "avg_travel_time": eng.get_average_travel_time(),
        }

    def analyze(self):
        k = self.knowledge
        waiting = self.observed["lane_waiting"]
        self.needs_switch = {}
        for iid in k.intersection_ids:
            current = k.current_phase[iid]
            num_phases = len(k.phase_lanes[iid])
            if k.phase_timer[iid] < k.min_green:
                self.needs_switch[iid] = False
                continue
            best_phase = current
            best_pressure = -float("inf")
            for phase_idx in range(num_phases):
                upstream = sum(waiting.get(l, 0) for l in k.phase_lanes[iid][phase_idx])
                downstream = sum(waiting.get(l, 0) for l in k.downstream_lanes[iid][phase_idx])
                pressure = upstream - downstream
                if pressure > best_pressure:
                    best_pressure = pressure
                    best_phase = phase_idx
            self.needs_switch[iid] = best_phase != current

    def plan(self):
        k = self.knowledge
        self.planned_phases = {}
        for iid in k.intersection_ids:
            if k.phase_timer[iid] >= k.max_green:
                current = k.current_phase[iid]
                num_phases = len(k.phase_lanes[iid])
                self.planned_phases[iid] = (current + 1) % num_phases
            elif self.needs_switch.get(iid, False):
                current = k.current_phase[iid]
                num_phases = len(k.phase_lanes[iid])
                self.planned_phases[iid] = (current + 1) % num_phases

    def execute(self):
        k = self.knowledge
        eng = self.model.engine
        for iid in k.intersection_ids:
            if iid in self.planned_phases:
                eng.set_tl_phase(iid, self.planned_phases[iid])
                k.current_phase[iid] = self.planned_phases[iid]
                k.phase_timer[iid] = 0
            else:
                k.phase_timer[iid] += 1
