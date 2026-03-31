import os

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

COLORS = {"baseline": "tab:blue", "pressure": "tab:gray", "mapek": "tab:orange"}

METRICS = [
    ("vehicle_count", "Vehicle Count"),
    ("total_waiting", "Total Waiting Vehicles"),
    ("avg_travel_time", "Avg Travel Time (s)"),
    ("network_pressure", "Network Pressure"),
    ("total_switches", "Phase Switches"),
    ("active_upstream_waiting", "Active Upstream Waiting"),
    ("active_downstream_waiting", "Active Downstream Waiting"),
    ("active_score", "Active Score"),
    ("pressure_weight", "Pressure Weight"),
    ("downstream_weight", "Downstream Weight"),
    ("switch_weight", "Switch Weight"),
]


def generate_plots(csv_path="results.csv", out_dir=".", prefix="plot"):
    df = pd.read_csv(csv_path)
    n_seeds = df["seed"].nunique()
    strategies = df["strategy"].unique()

    paths = []
    paths.append(_plot_bars(df, strategies, out_dir, prefix))
    paths.append(_plot_boxplot(df, strategies, out_dir, prefix))

    for col, label in METRICS:
        if col in df.columns:
            paths.append(_plot_metric_timeseries(df, n_seeds, strategies, col, label, out_dir, prefix))

    print(f"Plots saved to {out_dir}/ ({len(paths)} files)")


def _plot_metric_timeseries(df, n_seeds, strategies, metric, ylabel, out_dir, prefix):
    """Time-series plot for a single metric with 95% CI bands."""
    fig, ax = plt.subplots(figsize=(10, 5))

    for strat in strategies:
        sub = df[df["strategy"] == strat]
        grouped = sub.groupby("step")[metric]
        mean = grouped.mean()
        if n_seeds > 1:
            ci = 1.96 * grouped.std() / np.sqrt(n_seeds)
        else:
            ci = 0

        ax.plot(mean.index, mean.values, label=strat, color=COLORS.get(strat, "tab:red"))
        ax.fill_between(mean.index, mean - ci, mean + ci, alpha=0.2,
                        color=COLORS.get(strat, "tab:red"))

    ax.set_xlabel("Simulation Step")
    ax.set_ylabel(ylabel)
    ax.set_title(f"{ylabel} Over Simulation (95% CI)")
    ax.legend()
    fig.tight_layout()
    path = os.path.join(out_dir, f"{prefix}_{metric}.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _plot_bars(df, strategies, out_dir, prefix):
    """Bar chart of mean metrics with 95% CI error bars."""
    metrics = ["avg_travel_time", "total_waiting", "vehicle_count"]
    labels = ["Avg Travel Time (s)", "Total Waiting", "Vehicle Count"]

    seed_means = df.groupby(["strategy", "seed"])[metrics].mean().reset_index()
    n_seeds = seed_means.groupby("strategy")["seed"].nunique().iloc[0]

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    x = np.arange(len(strategies))

    for ax, metric, label in zip(axes, metrics, labels):
        means = []
        cis = []
        for strat in strategies:
            vals = seed_means[seed_means["strategy"] == strat][metric]
            means.append(vals.mean())
            if n_seeds > 1:
                cis.append(1.96 * vals.std() / np.sqrt(n_seeds))
            else:
                cis.append(0)
        ax.bar(x, means, 0.5, yerr=cis, capsize=5,
               color=[COLORS.get(s, "tab:red") for s in strategies])
        ax.set_xticks(x)
        ax.set_xticklabels(strategies)
        ax.set_ylabel(label)
        ax.set_title(label)

    fig.tight_layout()
    path = os.path.join(out_dir, f"{prefix}_bars.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _plot_boxplot(df, strategies, out_dir, prefix):
    """Box plot of final avg_travel_time across seeds."""
    last_step = df["step"].max()
    final = df[df["step"] == last_step]

    fig, ax = plt.subplots(figsize=(6, 5))
    data = [final[final["strategy"] == s]["avg_travel_time"].values
            for s in strategies]
    bp = ax.boxplot(data, tick_labels=strategies, patch_artist=True)
    for patch, strat in zip(bp["boxes"], strategies):
        patch.set_facecolor(COLORS.get(strat, "tab:red"))
        patch.set_alpha(0.6)

    ax.set_ylabel("Final Avg Travel Time (s)")
    ax.set_title("Distribution of Final Avg Travel Time Across Seeds")
    fig.tight_layout()
    path = os.path.join(out_dir, f"{prefix}_boxplot.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


if __name__ == "__main__":
    generate_plots()
