import os

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

COLORS = {"baseline": "tab:blue", "mapek": "tab:orange"}


def generate_plots(csv_path="results.csv", out_dir=".", prefix="plot"):
    df = pd.read_csv(csv_path)
    n_seeds = df["seed"].nunique()
    strategies = df["strategy"].unique()

    ts = _plot_timeseries(df, n_seeds, strategies, out_dir, prefix)
    bars = _plot_bars(df, strategies, out_dir, prefix)
    box = _plot_boxplot(df, strategies, out_dir, prefix)
    print(f"Plots saved: {ts}, {bars}, {box}")


def _plot_timeseries(df, n_seeds, strategies, out_dir, prefix):
    """Plot A: avg_travel_time over steps with 95% CI bands."""
    fig, ax = plt.subplots(figsize=(10, 5))

    for strat in strategies:
        sub = df[df["strategy"] == strat]
        grouped = sub.groupby("step")["avg_travel_time"]
        mean = grouped.mean()
        if n_seeds > 1:
            ci = 1.96 * grouped.std() / np.sqrt(n_seeds)
        else:
            ci = 0

        ax.plot(mean.index, mean.values, label=strat, color=COLORS.get(strat, "tab:gray"))
        ax.fill_between(mean.index, mean - ci, mean + ci, alpha=0.2,
                        color=COLORS.get(strat, "tab:gray"))

    ax.set_xlabel("Simulation Step")
    ax.set_ylabel("Avg Travel Time (s)")
    ax.set_title("Average Travel Time Over Simulation (95% CI)")
    ax.legend()
    fig.tight_layout()
    path = os.path.join(out_dir, f"{prefix}_timeseries.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _plot_bars(df, strategies, out_dir, prefix):
    """Plot B: bar chart of mean metrics with 95% CI error bars."""
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
               color=[COLORS.get(s, "tab:gray") for s in strategies])
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
    """Plot C: box plot of final avg_travel_time across seeds."""
    last_step = df["step"].max()
    final = df[df["step"] == last_step]

    fig, ax = plt.subplots(figsize=(6, 5))
    data = [final[final["strategy"] == s]["avg_travel_time"].values
            for s in strategies]
    bp = ax.boxplot(data, tick_labels=strategies, patch_artist=True)
    for patch, strat in zip(bp["boxes"], strategies):
        patch.set_facecolor(COLORS.get(strat, "tab:gray"))
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
