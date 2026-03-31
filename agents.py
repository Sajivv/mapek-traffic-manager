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

    # Adaptive heuristic weights
    pressure_weight: float = 1.0
    downstream_weight: float = 0.5
    switch_weight: float = 2.0

    # Default values to relax back toward
    default_pressure_weight: float = 1.0
    default_downstream_weight: float = 0.5
    default_switch_weight: float = 2.0

    # Adaptation settings
    adapt_interval: int = 20
    history_window: int = 20

    # Simple thresholds
    waiting_threshold: float = 140.0
    downstream_threshold: float = 140.0
    switch_threshold: float = 1.2  # average switches per control step across the network

    # Rolling history
    recent_waiting: list[float] = field(default_factory=list)
    recent_downstream: list[float] = field(default_factory=list)
    recent_switches: list[float] = field(default_factory=list)


class FixedTimingAgent(mesa.Agent):
    """Baseline: cycles phases on a fixed timer matching roadnet.json timing."""

    def __init__(self, model, knowledge, phase_duration=35):
        super().__init__(model)
        self.knowledge = knowledge
        self.phase_duration = phase_duration

        self.last_total_pressure: float = 0.0
        self.last_total_switches: int = 0
        self.last_active_upstream_waiting: float = 0.0
        self.last_active_downstream_waiting: float = 0.0
        self.last_active_score: float = 0.0

    def step(self):
        k = self.knowledge
        eng = self.model.engine
        waiting = eng.get_lane_waiting_vehicle_count()

        self.last_total_switches = 0
        total_pressure = 0.0
        total_upstream = 0.0
        total_downstream = 0.0
        total_score = 0.0

        for iid in k.intersection_ids:
            k.phase_timer[iid] += 1

            if k.phase_timer[iid] >= self.phase_duration:
                num_phases = len(k.phase_lanes[iid])
                k.current_phase[iid] = (k.current_phase[iid] + 1) % num_phases
                eng.set_tl_phase(iid, k.current_phase[iid])
                k.phase_timer[iid] = 0
                self.last_total_switches += 1

            phase = k.current_phase[iid]
            upstream = sum(waiting.get(l, 0) for l in k.phase_lanes[iid][phase])
            downstream = sum(waiting.get(l, 0) for l in k.downstream_lanes[iid][phase])
            pressure = upstream - downstream

            total_pressure += pressure
            total_upstream += upstream
            total_downstream += downstream
            total_score += (
                k.default_pressure_weight * pressure
                - k.default_downstream_weight * downstream
            )

        self.last_total_pressure = total_pressure
        self.last_active_upstream_waiting = total_upstream
        self.last_active_downstream_waiting = total_downstream
        self.last_active_score = total_score


class ManagerAgent(mesa.Agent):
    """MAPE-K autonomic manager using an adaptive heuristic."""

    def __init__(self, model, knowledge, strategy="adaptive"):
        super().__init__(model)
        self.knowledge = knowledge
        self.strategy = strategy

        self.observed: dict = {}
        self.best_phases: dict[str, int] = {}
        self.planned_phases: dict[str, int] = {}
        self.phase_scores: dict[str, dict[int, dict[str, float]]] = {}

        self.last_total_pressure: float = 0.0
        self.last_total_switches: int = 0
        self.last_active_upstream_waiting: float = 0.0
        self.last_active_downstream_waiting: float = 0.0
        self.last_active_score: float = 0.0

        self.control_step_count: int = 0

    def step(self):
        for iid in self.knowledge.intersection_ids:
            self.knowledge.phase_timer[iid] += 1

        self.monitor()
        self.analyze()
        self.plan()
        self.execute()
        self.update_step_metrics()

        self.control_step_count += 1
        if self.strategy == "adaptive" and self.control_step_count % self.knowledge.adapt_interval == 0:
            self.update_knowledge()

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
        self.phase_scores = {}

        for iid in k.intersection_ids:
            current = k.current_phase[iid]
            num_phases = len(k.phase_lanes[iid])
            self.phase_scores[iid] = {}

            for phase_idx in range(num_phases):
                upstream = sum(waiting.get(l, 0) for l in k.phase_lanes[iid][phase_idx])
                downstream = sum(waiting.get(l, 0) for l in k.downstream_lanes[iid][phase_idx])
                pressure = upstream - downstream
                switch_cost = 1 if phase_idx != current else 0

                score = (
                    k.pressure_weight * pressure
                    - k.downstream_weight * downstream
                    - k.switch_weight * switch_cost
                )

                self.phase_scores[iid][phase_idx] = {
                    "upstream": upstream,
                    "downstream": downstream,
                    "pressure": pressure,
                    "switch_cost": switch_cost,
                    "score": score,
                }

            if k.phase_timer[iid] < k.min_green:
                self.best_phases[iid] = current
                continue

            best_phase = current
            best_score = self.phase_scores[iid][current]["score"]

            for phase_idx in range(num_phases):
                if self.phase_scores[iid][phase_idx]["score"] > best_score:
                    best_score = self.phase_scores[iid][phase_idx]["score"]
                    best_phase = phase_idx

            self.best_phases[iid] = best_phase

    def plan(self):
        k = self.knowledge
        self.planned_phases = {}

        for iid in k.intersection_ids:
            current = k.current_phase[iid]
            num_phases = len(k.phase_lanes[iid])

            if k.phase_timer[iid] >= k.max_green:
                self.planned_phases[iid] = (current + 1) % num_phases
                continue

            best_phase = self.best_phases.get(iid, current)
            if best_phase != current:
                self.planned_phases[iid] = best_phase

    def execute(self):
        k = self.knowledge
        eng = self.model.engine
        self.last_total_switches = 0

        for iid in k.intersection_ids:
            if iid in self.planned_phases:
                eng.set_tl_phase(iid, self.planned_phases[iid])
                k.current_phase[iid] = self.planned_phases[iid]
                k.phase_timer[iid] = 0
                self.last_total_switches += 1

    def update_step_metrics(self):
        k = self.knowledge
        waiting = self.observed["lane_waiting"]

        total_pressure = 0.0
        total_upstream = 0.0
        total_downstream = 0.0
        total_score = 0.0

        for iid in k.intersection_ids:
            phase = k.current_phase[iid]
            upstream_lanes = k.phase_lanes[iid][phase]
            downstream_lanes = k.downstream_lanes[iid][phase]

            upstream = sum(waiting.get(l, 0) for l in upstream_lanes)
            downstream = sum(waiting.get(l, 0) for l in downstream_lanes)
            pressure = upstream - downstream

            total_pressure += pressure
            total_upstream += upstream
            total_downstream += downstream
            total_score += (
                k.pressure_weight * pressure
                - k.downstream_weight * downstream
            )

        self.last_total_pressure = total_pressure
        self.last_active_upstream_waiting = total_upstream
        self.last_active_downstream_waiting = total_downstream
        self.last_active_score = total_score

    def update_knowledge(self):
        k = self.knowledge
        total_waiting = sum(self.observed["lane_waiting"].values())
        avg_downstream_now = self.last_active_downstream_waiting
        total_switches = self.last_total_switches
    
        k.recent_waiting.append(total_waiting)
        k.recent_downstream.append(avg_downstream_now)
        k.recent_switches.append(total_switches)
    
        if len(k.recent_waiting) > k.history_window:
            k.recent_waiting.pop(0)
        if len(k.recent_downstream) > k.history_window:
            k.recent_downstream.pop(0)
        if len(k.recent_switches) > k.history_window:
            k.recent_switches.pop(0)
    
        avg_waiting = sum(k.recent_waiting) / len(k.recent_waiting)
        avg_downstream = sum(k.recent_downstream) / len(k.recent_downstream)
        avg_switches = sum(k.recent_switches) / len(k.recent_switches)
    
        # ---- pressure weight: emphasize only when waiting is high
        # and downstream is not already the dominant issue
        if avg_waiting > k.waiting_threshold and avg_downstream <= k.downstream_threshold:
            k.pressure_weight = min(k.pressure_weight + 0.1, 3.0)
        else:
            k.pressure_weight = max(k.pressure_weight - 0.05, k.default_pressure_weight)
    
        # ---- downstream weight: emphasize only when downstream congestion is high
        if avg_downstream > k.downstream_threshold:
            k.downstream_weight = min(k.downstream_weight + 0.1, 3.0)
        else:
            k.downstream_weight = max(k.downstream_weight - 0.05, k.default_downstream_weight)
    
        # ---- switch weight: respond to oscillation only
        if avg_switches > k.switch_threshold:
            k.switch_weight = min(k.switch_weight + 0.2, 5.0)
        else:
            k.switch_weight = max(k.switch_weight - 0.1, k.default_switch_weight)
