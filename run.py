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
