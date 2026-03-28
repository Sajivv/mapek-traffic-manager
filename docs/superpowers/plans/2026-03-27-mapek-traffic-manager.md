# MAPE-K Traffic Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a MAPE-K autonomic traffic signal controller on CityFlow + Mesa that demonstrably outperforms fixed-timing baseline, with CSV output for comparison.

**Architecture:** Mesa `TrafficModel` wraps a `cityflow.Engine`. A single `ManagerAgent` runs the MAPE-K loop (Monitor/Analyze/Plan/Execute) each step using MaxPressure analysis. Baseline mode runs CityFlow with no agent. Both export per-step metrics to a single CSV.

**Tech Stack:** Python 3, CityFlow, Mesa >= 3.0, pandas

---

### Task 1: Knowledge dataclass and ManagerAgent skeleton (`agents.py`)

**Files:**
- Create: `agents.py`

- [ ] **Step 1: Write the Knowledge dataclass**

```python
from dataclasses import dataclass, field

@dataclass
class Knowledge:
    min_green: int = 10
    max_green: int = 60
    intersection_ids: list = field(default_factory=list)
    phase_lanes: dict = field(default_factory=dict)
    downstream_lanes: dict = field(default_factory=dict)
    current_phase: dict = field(default_factory=dict)
    phase_timer: dict = field(default_factory=dict)
```

- [ ] **Step 2: Write the ManagerAgent class with MAPE-K method stubs**

```python
import mesa

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
```

- [ ] **Step 3: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('agents.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add agents.py
git commit -m "Add Knowledge dataclass and ManagerAgent with MAPE-K methods"
```

---

### Task 2: TrafficModel with topology parsing (`model.py`)

**Files:**
- Create: `model.py`

**Depends on:** Task 1 (imports from `agents.py`)

- [ ] **Step 1: Write TrafficModel with topology parsing and DataCollector**

```python
import json
import mesa
import cityflow
from agents import Knowledge, ManagerAgent

class TrafficModel(mesa.Model):
    def __init__(self, config_path="config.json", strategy=None, seed=42):
        super().__init__(seed=seed)
        self.engine = cityflow.Engine(config_path, thread_num=1)
        self.engine.set_random_seed(seed)
        self.strategy = strategy

        if strategy:
            knowledge = self._build_knowledge(config_path)
            self.manager = ManagerAgent(self, knowledge, strategy=strategy)
        else:
            self.manager = None

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
        roadnet_path = cfg.get("dir", "./") + cfg["roadnetFile"]
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
        if self.manager:
            self.manager.step()
        self.engine.next_step()
        self.datacollector.collect(self)
```

- [ ] **Step 2: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('model.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add model.py
git commit -m "Add TrafficModel with CityFlow integration and topology parsing"
```

---

### Task 3: Run script with baseline vs MAPE-K comparison (`run.py`)

**Files:**
- Create: `run.py`

**Depends on:** Task 2 (imports from `model.py`)

- [ ] **Step 1: Write run.py**

```python
import pandas as pd
from model import TrafficModel

STEPS = 3600
CONFIG = "config.json"

def run_simulation(strategy, label):
    model = TrafficModel(config_path=CONFIG, strategy=strategy)
    for _ in range(STEPS):
        model.step()
    df = model.datacollector.get_model_vars_dataframe()
    df["strategy"] = label
    df.index.name = "step"
    return df

if __name__ == "__main__":
    print("Running baseline (fixed-timing)...")
    baseline = run_simulation(strategy=None, label="baseline")

    print("Running MAPE-K (MaxPressure)...")
    mapek = run_simulation(strategy="pressure", label="mapek")

    results = pd.concat([baseline, mapek], ignore_index=False)
    results.to_csv("results.csv")
    print(f"Results saved to results.csv ({len(results)} rows)")

    for label, df in [("baseline", baseline), ("mapek", mapek)]:
        print(f"\n--- {label} ---")
        print(f"  Avg travel time: {df['avg_travel_time'].mean():.2f}s")
        print(f"  Avg waiting:     {df['total_waiting'].mean():.2f}")
        print(f"  Max waiting:     {df['total_waiting'].max()}")
```

- [ ] **Step 2: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('run.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add run.py
git commit -m "Add run script comparing baseline vs MAPE-K with CSV export"
```

---

### Task 4: Integration test — run the full simulation

**Files:**
- None created; this task validates Tasks 1-3

**Depends on:** Task 3

- [ ] **Step 1: Verify CityFlow and Mesa are installed**

Run: `python3 -c "import cityflow; import mesa; print('cityflow OK, mesa', mesa.__version__)"`
Expected: prints versions without error

- [ ] **Step 2: Run the full simulation**

Run: `cd /mnt/c/Users/Mit/OneDrive/Desktop/MSAI/Autonomic\ Computing/Module9/mapek-traffic-manager && python3 run.py`
Expected:
- Prints "Running baseline..." and "Running MAPE-K..."
- Creates `results.csv` with columns: `step, vehicle_count, total_waiting, avg_travel_time, strategy`
- Prints summary stats for both strategies
- MAPE-K should show lower avg_travel_time and/or lower avg waiting than baseline

- [ ] **Step 3: Verify CSV output**

Run: `python3 -c "import pandas as pd; df = pd.read_csv('results.csv'); print(df.shape); print(df.groupby('strategy')[['avg_travel_time','total_waiting']].mean())"`
Expected: 7200 rows (3600 per strategy), mean metrics printed per strategy

- [ ] **Step 4: Commit results.csv**

```bash
git add results.csv
git commit -m "Add simulation results comparing baseline vs MAPE-K"
```

---

### Task 5: Code review

**Files:**
- Review: `agents.py`, `model.py`, `run.py`

**Depends on:** Task 4

- [ ] **Step 1: Run code-reviewer agent**

Use the `superpowers:code-reviewer` subagent to review all three files against the design spec at `docs/superpowers/specs/2026-03-27-mapek-traffic-manager-design.md`. Check for:
- Correctness of MaxPressure pressure calculation
- Proper Mesa 3.x API usage (no deprecated schedulers)
- Knowledge state management (phase_timer increments, resets)
- Topology parsing matches roadnet.json structure
- DataCollector captures the right metrics

- [ ] **Step 2: Fix any issues found**

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "Address code review feedback"
```
