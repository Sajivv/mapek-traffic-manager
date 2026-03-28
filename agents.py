from dataclasses import dataclass, field

import mesa


@dataclass
class Knowledge:
    min_green: int = 5
    max_green: int = 45
    intersection_ids: list[str] = field(default_factory=list)
    phase_lanes: dict[str, dict[int, list[str]]] = field(default_factory=dict)
    downstream_lanes: dict[str, dict[int, list[str]]] = field(default_factory=dict)
    current_phase: dict[str, int] = field(default_factory=dict)
    phase_timer: dict[str, int] = field(default_factory=dict)


class FixedTimingAgent(mesa.Agent):
    """Baseline: cycles phases on a fixed timer matching roadnet.json timing."""

    def __init__(self, model, knowledge, phase_duration=35):
        super().__init__(model)
        self.knowledge = knowledge
        self.phase_duration = phase_duration

    def step(self):
        k = self.knowledge
        eng = self.model.engine
        for iid in k.intersection_ids:
            k.phase_timer[iid] += 1
            if k.phase_timer[iid] >= self.phase_duration:
                num_phases = len(k.phase_lanes[iid])
                k.current_phase[iid] = (k.current_phase[iid] + 1) % num_phases
                eng.set_tl_phase(iid, k.current_phase[iid])
                k.phase_timer[iid] = 0


class ManagerAgent(mesa.Agent):
    """MAPE-K autonomic manager using MaxPressure analysis."""

    def __init__(self, model, knowledge, strategy="pressure"):
        super().__init__(model)
        self.knowledge = knowledge
        self.strategy = strategy
        self.observed: dict = {}
        self.best_phases: dict[str, int] = {}
        self.planned_phases: dict[str, int] = {}

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
        self.best_phases = {}
        for iid in k.intersection_ids:
            current = k.current_phase[iid]
            num_phases = len(k.phase_lanes[iid])
            if k.phase_timer[iid] < k.min_green:
                self.best_phases[iid] = current
                continue
            # Compute current phase pressure as baseline; others must strictly exceed
            cur_up = sum(waiting.get(l, 0) for l in k.phase_lanes[iid][current])
            cur_dn = sum(waiting.get(l, 0) for l in k.downstream_lanes[iid][current])
            best_phase = current
            best_pressure = cur_up - cur_dn
            for phase_idx in range(num_phases):
                if phase_idx == current:
                    continue
                upstream = sum(waiting.get(l, 0) for l in k.phase_lanes[iid][phase_idx])
                downstream = sum(waiting.get(l, 0) for l in k.downstream_lanes[iid][phase_idx])
                pressure = upstream - downstream
                if pressure > best_pressure:
                    best_pressure = pressure
                    best_phase = phase_idx
            self.best_phases[iid] = best_phase

    def plan(self):
        k = self.knowledge
        self.planned_phases = {}
        for iid in k.intersection_ids:
            best = self.best_phases.get(iid, k.current_phase[iid])
            if best != k.current_phase[iid]:
                self.planned_phases[iid] = best
            elif k.phase_timer[iid] >= k.max_green:
                # Starvation guard: force round-robin if current is still best
                num_phases = len(k.phase_lanes[iid])
                self.planned_phases[iid] = (k.current_phase[iid] + 1) % num_phases

    def execute(self):
        k = self.knowledge
        eng = self.model.engine
        for iid in k.intersection_ids:
            k.phase_timer[iid] += 1
            if iid in self.planned_phases:
                eng.set_tl_phase(iid, self.planned_phases[iid])
                k.current_phase[iid] = self.planned_phases[iid]
                k.phase_timer[iid] = 0
