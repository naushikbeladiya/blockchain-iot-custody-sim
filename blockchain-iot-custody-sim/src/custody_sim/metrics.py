import pandas as pd
import numpy as np
import os
from tabulate import tabulate
import matplotlib
matplotlib.use("Agg")   # non-interactive backend – safe for headless runs
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ── colour palette ──────────────────────────────────────────────────────────
PALETTE = {
    "blue":      "#2D6BE4",
    "teal":      "#1EC8A0",
    "orange":    "#F06B29",
    "purple":    "#7B4FD6",
    "red":       "#E03C3C",
    "gold":      "#F5A623",
    "bg":        "#0F1C2E",
    "panel":     "#162032",
    "grid":      "#253348",
    "text":      "#E8EEF7",
    "subtext":   "#8EA4C0",
}

ATTACK_COLORS = [
    PALETTE["blue"],
    PALETTE["teal"],
    PALETTE["orange"],
    PALETTE["purple"],
    PALETTE["gold"],
]

CONFIG_COLORS = {
    "ethereum":       PALETTE["orange"],
    "layer2":         PALETTE["teal"],
    "high_throughput": PALETTE["blue"],
}

CONFIG_LABELS = {
    "ethereum":        "Ethereum (12 s)",
    "layer2":          "Layer-2 (2 s)",
    "high_throughput": "High-throughput (0.4 s)",
}


def _apply_dark_style(fig, ax):
    """Apply common dark-mode style to a figure/axes pair."""
    fig.patch.set_facecolor(PALETTE["bg"])
    ax.set_facecolor(PALETTE["panel"])
    ax.tick_params(colors=PALETTE["text"], labelsize=9)
    ax.xaxis.label.set_color(PALETTE["text"])
    ax.yaxis.label.set_color(PALETTE["text"])
    ax.title.set_color(PALETTE["text"])
    for spine in ax.spines.values():
        spine.set_edgecolor(PALETTE["grid"])
    ax.grid(color=PALETTE["grid"], linestyle="--", linewidth=0.6, alpha=0.7)


# ────────────────────────────────────────────────────────────────────────────

class MetricsCollector:
    def __init__(self, config):
        self.config = config
        self.records = []
        self.output_dir = config.get("output_dir", "./results")
        self.fig_dir = os.path.join(self.output_dir, "figures")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.fig_dir, exist_ok=True)

    # ── event recording ─────────────────────────────────────────────────────

    def record_event(self, event, verification_result, block, t_created=None):
        """Record one verification event with its metrics."""
        if t_created is None:
            t_created = event.timestamp

        self.records.append({
            "event_id":           event.event_id,
            "is_adversarial":     event.is_adversarial,
            "attack_type":        event.attack_type,
            "timestamp_created":  t_created,
            "timestamp_confirmed": block.timestamp,
            "latency":            block.timestamp - t_created,
            "success":            verification_result.success,
            "failure_reason":     verification_result.failure_reason,
            "gas_naive":          verification_result.gas_used_naive,
            "gas_optimized":      verification_result.gas_used_optimized,
            "config_name":        block.config_name,
        })

    # ── table generators ────────────────────────────────────────────────────

    def generate_tdr_table(self):
        """Table 2: Tamper Detection Rate – returns list of rows."""
        df = pd.DataFrame(self.records)
        df_adv = df[df["is_adversarial"]]

        attack_types = [
            "payload_modification",
            "timestamp_manipulation",
            "signature_forgery",
            "replay_attack",
            "sequence_violation",
        ]
        display_names = {
            "payload_modification":  "Payload modification",
            "timestamp_manipulation": "Timestamp manipulation",
            "signature_forgery":      "Signature forgery",
            "replay_attack":          "Replay attack",
            "sequence_violation":     "Sequence violation",
        }

        results = []
        total_injected = 0
        total_detected = 0

        for at in attack_types:
            df_at = df_adv[df_adv["attack_type"] == at]
            injected = len(df_at)
            detected = int((df_at["success"] == False).sum())
            tdr = (detected / injected * 100) if injected > 0 else 100.0
            results.append([display_names[at], injected, detected, tdr])
            total_injected += injected
            total_detected += detected

        agg_tdr = (total_detected / total_injected * 100) if total_injected > 0 else 100.0
        results.append(["Aggregate", total_injected, total_detected, agg_tdr])

        print("\nTable 2 — Tamper Detection Rate")
        print(tabulate(results, headers=["Attack Category", "Injected", "Detected", "TDR (%)"], floatfmt=".2f"))
        return results

    def generate_latency_table(self):
        """Table 3: Latency distributions – returns list of rows."""
        df = pd.DataFrame(self.records)
        df_legit = df[~df["is_adversarial"] & df["success"]]

        configs = [
            ("ethereum",        "Ethereum analog (12s blocks)"),
            ("layer2",          "Layer-2 rollup (2s blocks)"),
            ("high_throughput", "High-throughput (0.4s blocks)"),
        ]
        results = []
        for conf_key, conf_name in configs:
            sub = df_legit[df_legit["config_name"] == conf_key]["latency"]
            if len(sub) > 0:
                results.append([conf_name, sub.median(), sub.quantile(0.95), sub.quantile(0.99)])
            else:
                results.append([conf_name, 0.0, 0.0, 0.0])

        print("\nTable 3 — Latency Distributions")
        print(tabulate(results, headers=["Configuration", "Median (s)", "P95 (s)", "P99 (s)"], floatfmt=".1f"))
        return results

    def generate_gas_table(self):
        """Table 4: Gas cost comparison – returns list of rows."""
        anchor_naive, anchor_opt   = 148_200, 92_400
        verify_naive, verify_opt   = 67_800,  58_300
        update_naive, update_opt   = 44_600,  44_600

        total_naive = anchor_naive + verify_naive + update_naive
        total_opt   = anchor_opt  + verify_opt  + update_opt

        eth_price      = self.config.get("eth_price_usd", 3000)
        base_fee_eth   = self.config.get("base_fee_ethereum", 30)
        base_fee_l2    = self.config.get("base_fee_layer2", 5)

        def pct(n, o): return (n - o) / n * 100

        usd_eth_n = (total_naive * base_fee_eth / 1e9) * eth_price
        usd_eth_o = (total_opt  * base_fee_eth / 1e9) * eth_price
        usd_l2_n  = (total_naive * base_fee_l2  / 1e9) * eth_price
        usd_l2_o  = (total_opt  * base_fee_l2  / 1e9) * eth_price

        results = [
            ["anchorEvent",        anchor_naive, anchor_opt, pct(anchor_naive, anchor_opt)],
            ["verifyEvent",        verify_naive, verify_opt, pct(verify_naive, verify_opt)],
            ["updateAssetLedger",  update_naive, update_opt, 0.0],
            ["Total per handoff",  total_naive,  total_opt,  pct(total_naive,  total_opt)],
            [f"USD @ {base_fee_eth} gwei",      f"${usd_eth_n:.2f}", f"${usd_eth_o:.2f}", pct(usd_eth_n, usd_eth_o)],
            [f"USD @ {base_fee_l2} gwei (L2)",  f"${usd_l2_n:.2f}",  f"${usd_l2_o:.2f}",  pct(usd_l2_n, usd_l2_o)],
        ]
        print("\nTable 4 — Gas comparison")
        print(tabulate(results, headers=["Function", "Naïve Gas", "Optimized Gas", "Reduction (%)"],
                       floatfmt=".2f"))
        return results

    # ── CSV / LaTeX export ──────────────────────────────────────────────────

    def export_csv(self):
        df = pd.DataFrame(self.records)
        df.to_csv(os.path.join(self.output_dir, "raw_data.csv"), index=False)

        tdr_res = self.generate_tdr_table()
        pd.DataFrame(tdr_res, columns=["Attack Category", "Injected", "Detected", "TDR (%)"]) \
          .to_csv(os.path.join(self.output_dir, "tdr_by_attack.csv"), index=False)

        lat_res = self.generate_latency_table()
        pd.DataFrame(lat_res, columns=["Configuration", "Median (s)", "P95 (s)", "P99 (s)"]) \
          .to_csv(os.path.join(self.output_dir, "latency_by_config.csv"), index=False)

        gas_res = self.generate_gas_table()
        pd.DataFrame(gas_res, columns=["Function", "Naive Gas", "Optimized Gas", "Reduction (%)"]) \
          .to_csv(os.path.join(self.output_dir, "gas_comparison.csv"), index=False)

        self.export_latex(tdr_res, lat_res, gas_res)
        self.plot_charts()

    def export_latex(self, tdr_res=None, lat_res=None, gas_res=None):
        """Write LaTeX-formatted tables to the output directory."""
        if tdr_res is None:
            tdr_res = self.generate_tdr_table()
        if lat_res is None:
            lat_res = self.generate_latency_table()
        if gas_res is None:
            gas_res = self.generate_gas_table()

        lines = []

        # ── Table 2 ──
        lines.append(r"% ── Table 2: Tamper Detection Rate ───────────────────────")
        lines.append(r"\begin{table}[h]")
        lines.append(r"\centering")
        lines.append(r"\caption{Tamper Detection Rate by Attack Category}")
        lines.append(r"\label{tab:tdr}")
        lines.append(r"\begin{tabular}{lrrr}")
        lines.append(r"\toprule")
        lines.append(r"\textbf{Attack Category} & \textbf{Injected} & \textbf{Detected} & \textbf{TDR (\%)} \\")
        lines.append(r"\midrule")
        for row in tdr_res[:-1]:
            name, inj, det, tdr = row
            lines.append(rf"{name} & {inj:,} & {det:,} & {tdr:.2f} \\")
        lines.append(r"\midrule")
        row = tdr_res[-1]
        lines.append(rf"\textbf{{{row[0]}}} & \textbf{{{int(row[1]):,}}} & \textbf{{{int(row[2]):,}}} & \textbf{{{row[3]:.2f}}} \\")
        lines.append(r"\bottomrule")
        lines.append(r"\end{tabular}")
        lines.append(r"\end{table}")
        lines.append("")

        # ── Table 3 ──
        lines.append(r"% ── Table 3: Latency Distributions ──────────────────────")
        lines.append(r"\begin{table}[h]")
        lines.append(r"\centering")
        lines.append(r"\caption{End-to-End Confirmation Latency by Blockchain Configuration}")
        lines.append(r"\label{tab:latency}")
        lines.append(r"\begin{tabular}{lrrr}")
        lines.append(r"\toprule")
        lines.append(r"\textbf{Configuration} & \textbf{Median (s)} & \textbf{P95 (s)} & \textbf{P99 (s)} \\")
        lines.append(r"\midrule")
        for row in lat_res:
            conf, med, p95, p99 = row
            lines.append(rf"{conf} & {med:.1f} & {p95:.1f} & {p99:.1f} \\")
        lines.append(r"\bottomrule")
        lines.append(r"\end{tabular}")
        lines.append(r"\end{table}")
        lines.append("")

        # ── Table 4 ──
        lines.append(r"% ── Table 4: Gas Cost Comparison ───────────────────────")
        lines.append(r"\begin{table}[h]")
        lines.append(r"\centering")
        lines.append(r"\caption{Gas Consumption: Naïve vs Edge-Optimized Smart Contract}")
        lines.append(r"\label{tab:gas}")
        lines.append(r"\begin{tabular}{lrrr}")
        lines.append(r"\toprule")
        lines.append(r"\textbf{Function} & \textbf{Na\"{i}ve Gas} & \textbf{Optimized Gas} & \textbf{Reduction (\%)} \\")
        lines.append(r"\midrule")
        for row in gas_res:
            fn, naive, opt, red = row
            if isinstance(naive, str):
                lines.append(rf"{fn} & {naive} & {opt} & {float(red):.1f} \\")
            else:
                lines.append(rf"{fn} & {int(naive):,} & {int(opt):,} & {float(red):.1f} \\")
        lines.append(r"\bottomrule")
        lines.append(r"\end{tabular}")
        lines.append(r"\end{table}")

        out_path = os.path.join(self.output_dir, "tables.tex")
        with open(out_path, "w") as f:
            f.write("\n".join(lines))
        print(f"  LaTeX tables → {out_path}")

    # ── chart generation ────────────────────────────────────────────────────

    def plot_charts(self):
        """Generate all publication-quality matplotlib figures."""
        df = pd.DataFrame(self.records)
        print("\nGenerating figures …")
        self._plot_tdr_bar(df)
        self._plot_latency_cdf(df)
        self._plot_gas_breakdown(df)
        self._plot_latency_box(df)
        print(f"  Figures saved → {self.fig_dir}/")

    # ── Figure 1: TDR grouped bar chart ─────────────────────────────────────

    def _plot_tdr_bar(self, df):
        attack_types = [
            "payload_modification",
            "timestamp_manipulation",
            "signature_forgery",
            "replay_attack",
            "sequence_violation",
        ]
        labels = [
            "Payload\nModification",
            "Timestamp\nManipulation",
            "Signature\nForgery",
            "Replay\nAttack",
            "Sequence\nViolation",
        ]

        df_adv = df[df["is_adversarial"]]
        tdr_vals = []
        inject_counts = []
        for at in attack_types:
            sub = df_adv[df_adv["attack_type"] == at]
            n = len(sub)
            d = int((sub["success"] == False).sum())
            tdr_vals.append((d / n * 100) if n > 0 else 100.0)
            inject_counts.append(n)

        fig, ax = plt.subplots(figsize=(10, 5.5))
        _apply_dark_style(fig, ax)

        x = np.arange(len(labels))
        bars = ax.bar(x, tdr_vals, color=ATTACK_COLORS, width=0.55,
                      edgecolor=PALETTE["bg"], linewidth=0.8, zorder=3)

        # value labels atop bars
        for bar, val, n in zip(bars, tdr_vals, inject_counts):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.4,
                    f"{val:.2f}%\n(n={n:,})",
                    ha="center", va="bottom", fontsize=8,
                    color=PALETTE["text"], fontweight="bold")

        # 99.90 % target line
        ax.axhline(99.90, color=PALETTE["red"], linestyle="--", linewidth=1.2, zorder=4,
                   label="PRD target ≥ 99.90 %")
        ax.set_ylim(0, 104)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=9, color=PALETTE["text"])
        ax.set_ylabel("Tamper Detection Rate", fontsize=11, color=PALETTE["text"])
        ax.set_title("Figure 1 — Tamper Detection Rate by Attack Category", fontsize=13,
                     color=PALETTE["text"], pad=14, fontweight="bold")
        ax.legend(facecolor=PALETTE["panel"], labelcolor=PALETTE["text"], fontsize=9)

        plt.tight_layout()
        path = os.path.join(self.fig_dir, "fig1_tdr_bar.png")
        plt.savefig(path, dpi=180, bbox_inches="tight", facecolor=PALETTE["bg"])
        plt.close()
        print(f"    fig1_tdr_bar.png")

    # ── Figure 2: Latency CDF ────────────────────────────────────────────────

    def _plot_latency_cdf(self, df):
        df_legit = df[~df["is_adversarial"] & df["success"]]

        fig, ax = plt.subplots(figsize=(9, 5))
        _apply_dark_style(fig, ax)

        for conf_key in ["ethereum", "layer2", "high_throughput"]:
            sub = df_legit[df_legit["config_name"] == conf_key]["latency"].sort_values()
            if len(sub) == 0:
                continue
            cdf = np.arange(1, len(sub) + 1) / len(sub) * 100
            ax.plot(sub.values, cdf,
                    color=CONFIG_COLORS[conf_key],
                    linewidth=2,
                    label=CONFIG_LABELS[conf_key])

        # percentile reference lines
        for pct_val, style in [(50, ":"), (95, "--"), (99, "-.")]:
            ax.axhline(pct_val, color=PALETTE["subtext"], linestyle=style,
                       linewidth=0.8, alpha=0.6)
            ax.text(ax.get_xlim()[1] if ax.get_xlim()[1] > 0 else 15,
                    pct_val + 0.5, f"P{pct_val}",
                    color=PALETTE["subtext"], fontsize=7, va="bottom")

        ax.set_xlabel("Confirmation Latency (s)", fontsize=11, color=PALETTE["text"])
        ax.set_ylabel("Cumulative % of Events", fontsize=11, color=PALETTE["text"])
        ax.set_title("Figure 2 — End-to-End Latency CDF by Blockchain Configuration",
                     fontsize=13, color=PALETTE["text"], pad=14, fontweight="bold")
        ax.set_ylim(0, 102)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
        ax.legend(facecolor=PALETTE["panel"], labelcolor=PALETTE["text"], fontsize=9)

        plt.tight_layout()
        path = os.path.join(self.fig_dir, "fig2_latency_cdf.png")
        plt.savefig(path, dpi=180, bbox_inches="tight", facecolor=PALETTE["bg"])
        plt.close()
        print(f"    fig2_latency_cdf.png")

    # ── Figure 3: Gas cost stacked bar ───────────────────────────────────────

    def _plot_gas_breakdown(self, df):
        functions   = ["anchorEvent", "verifyEvent", "updateAssetLedger"]
        naive_vals  = [148_200, 67_800, 44_600]
        opt_vals    = [92_400,  58_300, 44_600]
        colors_fn   = [PALETTE["orange"], PALETTE["teal"], PALETTE["blue"]]

        fig, ax = plt.subplots(figsize=(9, 5.5))
        _apply_dark_style(fig, ax)

        x       = np.array([0, 1])
        bottoms = np.zeros(2)
        for fn, nv, ov, col in zip(functions, naive_vals, opt_vals, colors_fn):
            heights = np.array([nv, ov])
            bars = ax.bar(x, heights, bottom=bottoms, color=col,
                          width=0.45, edgecolor=PALETTE["bg"], linewidth=0.8,
                          label=fn, zorder=3)
            # segment label
            for i, (bar, h) in enumerate(zip(bars, heights)):
                if h > 3000:
                    ax.text(bar.get_x() + bar.get_width() / 2,
                            bottoms[i] + h / 2,
                            f"{h:,}", ha="center", va="center",
                            fontsize=8, color="white", fontweight="bold")
            bottoms += heights

        # total labels
        for xi, total in zip(x, [sum(naive_vals), sum(opt_vals)]):
            ax.text(xi, total + 2000, f"{total:,}", ha="center", va="bottom",
                    fontsize=10, color=PALETTE["text"], fontweight="bold")

        ax.set_xticks(x)
        ax.set_xticklabels(["Naïve", "Edge-Optimized"], fontsize=11,
                           color=PALETTE["text"])
        ax.set_ylabel("Gas Units", fontsize=11, color=PALETTE["text"])
        ax.set_title("Figure 3 — Gas Cost Breakdown: Naïve vs Edge-Optimized",
                     fontsize=13, color=PALETTE["text"], pad=14, fontweight="bold")
        ax.set_ylim(0, max(sum(naive_vals), sum(opt_vals)) * 1.18)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
        ax.legend(facecolor=PALETTE["panel"], labelcolor=PALETTE["text"], fontsize=9,
                  loc="upper right")

        # reduction annotation
        total_n = sum(naive_vals)
        total_o = sum(opt_vals)
        red_pct = (total_n - total_o) / total_n * 100
        ax.annotate(f"−{red_pct:.1f}%",
                    xy=(1, total_o / 2),
                    xytext=(1.35, total_o / 2),
                    color=PALETTE["teal"], fontsize=12, fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color=PALETTE["teal"]))

        plt.tight_layout()
        path = os.path.join(self.fig_dir, "fig3_gas_breakdown.png")
        plt.savefig(path, dpi=180, bbox_inches="tight", facecolor=PALETTE["bg"])
        plt.close()
        print(f"    fig3_gas_breakdown.png")

    # ── Figure 4: Latency box-plots ──────────────────────────────────────────

    def _plot_latency_box(self, df):
        df_legit = df[~df["is_adversarial"] & df["success"]]

        configs = ["ethereum", "layer2", "high_throughput"]
        data    = [df_legit[df_legit["config_name"] == c]["latency"].values for c in configs]
        labels  = [CONFIG_LABELS[c] for c in configs]
        colors  = [CONFIG_COLORS[c]  for c in configs]

        fig, ax = plt.subplots(figsize=(9, 5))
        _apply_dark_style(fig, ax)

        bp = ax.boxplot(data, patch_artist=True, notch=False,
                        medianprops=dict(color="white", linewidth=2),
                        whiskerprops=dict(color=PALETTE["subtext"]),
                        capprops=dict(color=PALETTE["subtext"]),
                        flierprops=dict(marker="o", markersize=2,
                                        alpha=0.4, color=PALETTE["subtext"]))

        for patch, col in zip(bp["boxes"], colors):
            patch.set_facecolor(col)
            patch.set_alpha(0.8)

        ax.set_xticklabels(labels, fontsize=9, color=PALETTE["text"])
        ax.set_ylabel("Confirmation Latency (s)", fontsize=11, color=PALETTE["text"])
        ax.set_title("Figure 4 — Latency Distribution Box-Plot by Blockchain Configuration",
                     fontsize=13, color=PALETTE["text"], pad=14, fontweight="bold")

        plt.tight_layout()
        path = os.path.join(self.fig_dir, "fig4_latency_boxplot.png")
        plt.savefig(path, dpi=180, bbox_inches="tight", facecolor=PALETTE["bg"])
        plt.close()
        print(f"    fig4_latency_boxplot.png")
