# MAPE-K Traffic Manager Design Spec

## Goal

Demonstrate that a MAPE-K autonomic manager using MaxPressure analysis outperforms fixed-timing traffic signal control on a CityFlow 3x3 grid network. Output comparison metrics as CSV.

## Architecture

- **Simulation engine**: CityFlow (`cityflow.Engine`) with `rlTrafficLight: true`
- **Agent framework**: Mesa 3.x — `TrafficModel(mesa.Model)` wraps CityFlow; `ManagerAgent(mesa.Agent)` runs the MAPE-K loop
- **Pattern**: Single centralized MAPE-K manager controlling all 9 intersections
- **Comparison**: Baseline (CityFlow fixed-timing, no agent) vs MAPE-K (MaxPressure)

## File Structure

```
model.py    (~60 lines)  Mesa Model wrapping CityFlow, DataCollector, topology parsing
agents.py   (~80 lines)  ManagerAgent with M-A-P-E methods, Knowledge dataclass
run.py      (~40 lines)  Entry point: runs baseline + MAPE-K, exports results.csv
```

Existing files unchanged: `config.json`, `roadnet.json`, `flow.json`.

## Knowledge Structure

```python
@dataclass
class Knowledge:
    # Policy (tunable parameters for experimentation)
    min_green: int = 5
    max_green: int = 45
    # Runtime (per intersection)
    current_phase: dict[str, int]
    phase_timer: dict[str, int]

    # Topology (from roadnet.json, built once at init)
    intersection_ids: list[str]
    phase_lanes: dict[str, dict[int, list[str]]]       # upstream lanes per phase
    downstream_lanes: dict[str, dict[int, list[str]]]   # downstream lanes per phase
```

## MAPE-K Data Flow (Per Step)

### Monitor
Reads from CityFlow engine:
- `eng.get_lane_vehicle_count()` -> lane vehicle counts
- `eng.get_lane_waiting_vehicle_count()` -> lane waiting counts
- `eng.get_average_travel_time()` -> average travel time

Stores snapshot in `self.observed`.

### Analyze (MaxPressure)
For each intersection and each phase:
- `pressure[phase] = sum(upstream_waiting) - sum(downstream_waiting)`
- Identify the phase with highest pressure; prefer current phase on ties
- Store the best phase per intersection

Note: On this single-lane-per-road topology, downstream lanes are identical across all phases, so pressure effectively reduces to max-upstream-waiting. This is still valid but means the downstream component adds no discriminating value.

Stores `self.best_phases: dict[str, int]`.

### Plan
If best phase differs from current, plan the switch to that phase directly.
Force switch if `phase_timer >= max_green`; use round-robin as starvation guard.
Note: CityFlow handles yellow time internally when `rlTrafficLight=true`; agents do not add yellow offset to timers.

Stores `self.planned_phases: dict[str, int]`.

### Execute
For each planned phase change:
- `eng.set_tl_phase(intersection_id, phase_id)`
- Reset `knowledge.phase_timer[id] = 0`
- Update `knowledge.current_phase[id]`

Increment `phase_timer` for non-switched intersections.

## TrafficModel.step()

```
if manager_agent exists:
    manager_agent.step()     # runs M-A-P-E
eng.next_step()              # advance CityFlow
datacollector.collect(self)  # record metrics
```

Baseline mode: FixedTimingAgent cycles phases every 35+yellowTime steps (matching roadnet.json timing). Required because `rlTrafficLight=true` disables CityFlow's internal signal controller.

## Topology Parsing

At init, `TrafficModel` parses `roadnet.json` to build the `phase_lanes` and `downstream_lanes` mappings:

1. For each intersection, read `trafficLight.lightphases`
2. Each phase's `availableRoadLinks` indices map to `roadLinks` entries
3. Each roadLink has `startRoad` (upstream) and `endRoad` (downstream)
4. Lane IDs = `{road_id}_{lane_index}` (this network has 1 lane per road, so index is always 0)

## Run Script

1. Run baseline: `TrafficModel(config_path, strategy=None)` for 3600 steps
2. Run MAPE-K: `TrafficModel(config_path, strategy="pressure")` for 3600 steps
3. Export single `results.csv` with columns: `step, vehicle_count, total_waiting, avg_travel_time, strategy`

## Dependencies

- `cityflow` (CityFlow Python bindings)
- `mesa` (>= 3.0)
- `pandas` (for CSV export via Mesa DataCollector)

## Constraints

- Skeleton code: configurable, simple, short, easy to read
- Each MAPE-K function is a separate method for clarity and independent testability
- No plotting libraries — CSV output only
- Strategy is a string parameter ("pressure" or None for baseline)
