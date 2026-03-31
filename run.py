import os
import sys
from datetime import datetime

import pandas as pd
from tqdm import tqdm
from model import TrafficModel
from plots import generate_plots

STEPS = 3600
CONFIG = "config.json"
N_RUNS = 1000


def run_simulation(strategy, label, seed):
    model = TrafficModel(config_path=CONFIG, strategy=strategy, seed=seed)
    for _ in range(STEPS):
        model.step()
    df = model.datacollector.get_model_vars_dataframe()
    df["strategy"] = label
    df["seed"] = seed
    df.index.name = "step"
    return df


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "run"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir = os.path.join("experiments", f"{name}_{timestamp}")
    os.makedirs(out_dir, exist_ok=True)

    all_results = []
    for run in tqdm(range(N_RUNS), desc="Simulations"):
        baseline = run_simulation(strategy=None, label="baseline", seed=run)
        mapek = run_simulation(strategy="pressure", label="mapek", seed=run)
        all_results.append(baseline)
        all_results.append(mapek)

    results = pd.concat(all_results, ignore_index=False)
    csv_path = os.path.join(out_dir, f"{name}_results.csv")
    results.to_csv(csv_path)
    print(f"Results saved to {csv_path} ({len(results)} rows)")

    # Summary stats across seeds
    seed_means = results.groupby(["strategy", "seed"])["avg_travel_time"].mean()
    for strat in results["strategy"].unique():
        vals = seed_means[strat]
        print(f"\n--- {strat} ({N_RUNS} runs) ---")
        print(f"  Avg travel time: {vals.mean():.2f} +/- {vals.std():.2f}s")

    generate_plots(csv_path, out_dir=out_dir, prefix=name)
