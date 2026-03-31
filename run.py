import pandas as pd
from model import TrafficModel

STEPS = 3600

SCENARIOS = [
    ("base", "config.json"),
    ("heavy_asym", "config_heavy_asym.json"),
]

def run_simulation(config_path, strategy, label, scenario):
    model = TrafficModel(config_path=config_path, strategy=strategy)
    for _ in range(STEPS):
        model.step()
    df = model.datacollector.get_model_vars_dataframe()
    df["label"] = label
    df["scenario"] = scenario
    df.index.name = "step"
    return df

if __name__ == "__main__":
    all_results = []

    for scenario_name, config_path in SCENARIOS:
        print(f"\n=== Scenario: {scenario_name} ===")

        print("Running baseline (fixed-timing)...")
        baseline = run_simulation(config_path, None, "baseline", scenario_name)

        print("Running pressure heuristic...")
        pressure = run_simulation(config_path, "pressure", "pressure", scenario_name)

        print("Running MAPE-K (adaptive)...")
        mapek = run_simulation(config_path, "adaptive", "mapek", scenario_name)

        for label, result_df in [("baseline", baseline), ("pressure", pressure), ("mapek", mapek)]:
            print(f"\n--- {scenario_name} / {label} ---")
            print(f"  Avg travel time:         {result_df['avg_travel_time'].mean():.2f}s")
            print(f"  Avg waiting:             {result_df['total_waiting'].mean():.2f}")
            print(f"  Max waiting:             {result_df['total_waiting'].max()}")
            print(f"  Avg network pressure:    {result_df['network_pressure'].mean():.2f}")
            print(f"  Total phase switches:    {result_df['total_switches'].sum()}")
            print(f"  Avg active upstream q:   {result_df['active_upstream_waiting'].mean():.2f}")
            print(f"  Avg active downstream q: {result_df['active_downstream_waiting'].mean():.2f}")
            print(f"  Final pressure weight:   {result_df['pressure_weight'].iloc[-1]:.2f}")
            print(f"  Final downstream weight: {result_df['downstream_weight'].iloc[-1]:.2f}")
            print(f"  Final switch weight:     {result_df['switch_weight'].iloc[-1]:.2f}")

        all_results.extend([baseline, pressure, mapek])

    df = pd.concat(all_results, ignore_index=True)
    df.to_csv("results_two_scenarios.csv", index=False)
    print(f"\nResults saved to results_two_scenarios.csv ({len(df)} rows)")
