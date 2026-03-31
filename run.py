import os
import sys
from datetime import datetime

import pandas as pd
from tqdm import tqdm
from model import TrafficModel
from plots import generate_plots

STEPS = 3600
N_RUNS = 100

SCENARIOS = [
    ("base", "config.json"),
    ("heavy_asym", "config_heavy_asym.json"),
]

STRATEGIES = [
    (None, "baseline"),
    ("pressure", "pressure"),
    ("adaptive", "mapek"),
]


def run_simulation(config_path, strategy, label, scenario, seed):
    model = TrafficModel(config_path=config_path, strategy=strategy, seed=seed)
    for _ in range(STEPS):
        model.step()
    df = model.datacollector.get_model_vars_dataframe()
    df["strategy"] = label
    df["scenario"] = scenario
    df["seed"] = seed
    df.index.name = "step"
    return df


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "run"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir = os.path.join("experiments", f"{name}_{timestamp}")
    os.makedirs(out_dir, exist_ok=True)

    all_results = []
    total = N_RUNS * len(SCENARIOS) * len(STRATEGIES)

    with tqdm(total=total, desc="Simulations") as pbar:
        for seed in range(N_RUNS):
            for scenario_name, config_path in SCENARIOS:
                for strategy, label in STRATEGIES:
                    df = run_simulation(config_path, strategy, label, scenario_name, seed)
                    all_results.append(df)
                    pbar.update(1)

    results = pd.concat(all_results, ignore_index=False)
    csv_path = os.path.join(out_dir, f"{name}_results.csv")
    results.to_csv(csv_path)
    print(f"Results saved to {csv_path} ({len(results)} rows)")

    # Summary stats per scenario and strategy
    seed_means = results.groupby(["scenario", "strategy", "seed"])["avg_travel_time"].mean()
    for scenario_name, _ in SCENARIOS:
        print(f"\n=== {scenario_name} ===")
        for _, label in STRATEGIES:
            vals = seed_means[scenario_name][label]
            print(f"  {label}: {vals.mean():.2f} +/- {vals.std():.2f}s")

    generate_plots(csv_path, out_dir=out_dir, prefix=name)
