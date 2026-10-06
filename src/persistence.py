"""Persistence of RCA: 2024 against 1989, for the UK and its G7 peers.

For each country we regress symmetric RCA in the later year on symmetric RCA
in 1989 across products (unweighted OLS, as in the report's Figure 14) and
report the slope, its 95% confidence interval and R². A slope and R² near 1
mean the pattern of specialisation has barely changed.

Products are left out of a country's regression when:
* they are the volatile categories the report drops from the ranking
  (gold, coin, miscellaneous manufactures), or
* the country has zero exports of them in either year. For a G7 economy
  at this level of aggregation a zero is a gap in the data rather than a real
  zero (e.g. the Atlas has no UK financial services before 1986 and no
  Japanese services at all before 1996).

Two versions:
* goods + services: the main analysis. Japan's 1989 totals exclude services
  because the Atlas has none, so its result is not like for like.
* goods only: RCA recomputed using goods-only totals for every country and
  the world, which is comparable across all seven.

Run after download.py:  python src/persistence.py
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

import rca

G7 = ["GBR", "USA", "DEU", "FRA", "ITA", "JPN", "CAN"]
G7_NAMES = {"GBR": "UK", "USA": "US", "DEU": "Germany", "FRA": "France",
            "ITA": "Italy", "JPN": "Japan", "CAN": "Canada"}
BASE_YEAR = 1989
COMPARE_YEARS = [2019, 2024]  # 2019 is the report's comparison year

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE = "#2a78d6", "#eb6834"


def paired(df: pd.DataFrame, country: str, year: int) -> pd.DataFrame:
    """One row per product: symmetric RCA in BASE_YEAR (x) and `year` (y)."""
    d = df[(df.country == country) & df.year.isin([BASE_YEAR, year])
           & ~df["product"].isin(rca.DROP_FROM_RANKING)]
    wide = d.pivot_table(index=["product", "product_name", "sector"], columns="year",
                         values=["rca_sym", "export_value"])
    keep = (wide["export_value"] > 0).all(axis=1)
    out = wide["rca_sym"][keep].reset_index()
    return out.rename(columns={BASE_YEAR: "x", year: "y"})


def ols(x: np.ndarray, y: np.ndarray) -> dict:
    """Slope, intercept, R² and a 95% CI for the slope."""
    n = len(x)
    X = np.column_stack([np.ones(n), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    r2 = 1 - (resid @ resid) / ((y - y.mean()) @ (y - y.mean()))
    se = np.sqrt((resid @ resid) / (n - 2) / ((x - x.mean()) @ (x - x.mean())))
    t = stats.t.ppf(0.975, n - 2)
    return {"n": n, "intercept": beta[0], "slope": beta[1], "slope_lo": beta[1] - t * se,
            "slope_hi": beta[1] + t * se, "r2": r2}


def goods_only(df: pd.DataFrame) -> pd.DataFrame:
    """Recompute RCA with goods-only country and world totals."""
    g = df[df.sector == "goods"][["country", "year", "product", "product_name", "sector", "export_value"]].copy()
    return rca.add_rca(g)


def results(variants: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for variant, df in variants.items():
        for c in G7:
            for y in COMPARE_YEARS:
                p = paired(df, c, y)
                rows.append({"variant": variant, "country": c, "country_name": G7_NAMES[c],
                             "base_year": BASE_YEAR, "year": y,
                             **ols(p.x.to_numpy(), p.y.to_numpy())})
    return pd.DataFrame(rows)


def style(ax) -> None:
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.plot([-1, 1], [-1, 1], color=MUTED, lw=0.8, ls=(0, (3, 3)))  # 45°: no change
    ax.set_xlim(-1, 1)
    ax.set_ylim(-1, 1)
    ax.set_aspect("equal")
    ax.set_xticks([-1, -0.5, 0, 0.5, 1])
    ax.set_yticks([-1, -0.5, 0, 0.5, 1])
    ax.grid(color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)


def fit_line(ax, fit: dict, colour: str) -> None:
    xs = np.array([-1, 1])
    ax.plot(xs, fit["intercept"] + fit["slope"] * xs, color=colour, lw=2, zorder=2)


def uk_scatter(df: pd.DataFrame, path) -> dict:
    """UK products, 1989 against 2024, with the fitted line and labels for the leaders."""
    p = paired(df, "GBR", 2024)
    fit = ols(p.x.to_numpy(), p.y.to_numpy())

    fig, ax = plt.subplots(figsize=(8.5, 8.5))
    style(ax)
    fit_line(ax, fit, BLUE)
    for sector, marker in (("goods", "o"), ("services", "D")):
        s = p[p.sector == sector]
        ax.scatter(s.x, s.y, s=40 if marker == "o" else 46, marker=marker, color=BLUE,
                   edgecolor="white", linewidth=1.2, zorder=3, label=sector.capitalize())
    # Label anything in the top 10 in either year.
    top = set(rca.top_n(df, "GBR", BASE_YEAR)["product"]) | set(rca.top_n(df, "GBR", 2024)["product"])
    # Labels sit to the right of each point; where points cluster, push labels
    # apart vertically (top down) and join them to their point with a thin line.
    lab = p[p["product"].isin(top)].sort_values("y", ascending=False)
    placed: list[tuple[float, float]] = []  # (x, label y) of labels already placed
    min_gap = 0.045
    for _, r in lab.iterrows():
        ly = r.y
        for px, py in placed:
            if abs(px - r.x) < 0.45 and ly > py - min_gap:
                ly = py - min_gap
        placed.append((r.x, ly))
        name = r.product_name if len(r.product_name) <= 32 else r.product_name[:31] + "…"
        ax.annotate(name, (r.x, r.y), xytext=(r.x + 0.04, ly), textcoords="data", va="center",
                    fontsize=7.5, color=INK,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.5, shrinkA=0, shrinkB=3))
    ax.set_xlabel(f"Symmetric RCA, {BASE_YEAR}", color=MUTED, fontsize=9)
    ax.set_ylabel("Symmetric RCA, 2024", color=MUTED, fontsize=9)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    fig.text(0.02, 0.985, f"UK revealed comparative advantage: {BASE_YEAR} vs 2024", va="top", fontsize=12, color=INK)
    fig.text(0.02, 0.955,
             f"R² = {fit['r2']:.2f}, slope = {fit['slope']:.2f} (95% CI {fit['slope_lo']:.2f} to {fit['slope_hi']:.2f}), "
             f"n = {fit['n']} products. Dashed line = no change. Labelled: top 10 in either year.",
             va="top", fontsize=8.5, color=MUTED)
    fig.text(0.02, 0.005, "Source: Harvard Growth Lab, Atlas of Economic Complexity (SITC Rev.2 goods + services).",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 0.94))
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return fit


def g7_scatter(df: pd.DataFrame, res: pd.DataFrame, path) -> None:
    """Small multiples: one 1989-vs-2024 scatter per G7 country."""
    fig, axes = plt.subplots(2, 4, figsize=(13, 7.2), sharex=True, sharey=True)
    for ax, c in zip(axes.flat, G7):
        p = paired(df, c, 2024)
        fit = res.query("variant == 'goods_and_services' and country == @c and year == 2024").iloc[0]
        style(ax)
        fit_line(ax, fit, BLUE)
        ax.scatter(p.x, p.y, s=18, color=BLUE, edgecolor="white", linewidth=0.8, zorder=3)
        flag = "*" if c == "JPN" else ""
        ax.set_title(f"{G7_NAMES[c]}{flag}   R² {fit.r2:.2f} · slope {fit.slope:.2f}",
                     fontsize=9.5, loc="left", color=INK, fontweight="bold" if c == "GBR" else "normal")
    axes.flat[-1].set_visible(False)
    for ax in axes[:, 0]:
        ax.set_ylabel("2024", color=MUTED, fontsize=9)
    for ax in axes[-1, :]:
        ax.set_xlabel(str(BASE_YEAR), color=MUTED, fontsize=9)
    axes[0, -1].set_xlabel(str(BASE_YEAR), color=MUTED, fontsize=9)
    axes[0, -1].tick_params(labelbottom=True)
    fig.suptitle(f"Symmetric RCA by product, {BASE_YEAR} vs 2024: G7", x=0.01, ha="left", fontsize=12, color=INK)
    fig.text(0.01, 0.005,
             "Goods + services. Dashed line = no change. *Japan: no Atlas services before 1996, so its 1989 services are "
             "excluded and its 1989 totals are goods only. Source: Harvard Growth Lab, Atlas of Economic Complexity.",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def g7_bars(res: pd.DataFrame, path) -> None:
    """R² of 2024 on 1989, by country, for both versions."""
    r = res[res.year == 2024]
    order = (r[r.variant == "goods_only"].sort_values("r2", ascending=False).country.tolist())
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    width = 0.38
    for i, (variant, colour, label) in enumerate([("goods_and_services", BLUE, "Goods + services"),
                                                  ("goods_only", ORANGE, "Goods only")]):
        v = r[r.variant == variant].set_index("country").loc[order]
        xs = np.arange(len(order)) + (i - 0.5) * (width + 0.02)
        ax.bar(xs, v.r2, width=width, color=colour, label=label, zorder=2)
        for x, val in zip(xs, v.r2):
            ax.text(x, val + 0.015, f"{val:.2f}", ha="center", fontsize=7.5, color=INK)
    ax.set_xticks(np.arange(len(order)),
                  [G7_NAMES[c] + ("*" if c == "JPN" else "") for c in order], fontsize=9, color=INK)
    ax.set_ylim(0, 1)
    ax.set_ylabel("R²", color=MUTED, fontsize=9)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=MUTED, length=0)
    ax.legend(frameon=False, fontsize=9, loc="upper right", ncols=2)
    fig.text(0.01, 0.985, f"How much of each country's 2024 RCA pattern is explained by {BASE_YEAR}?",
             va="top", fontsize=12, color=INK)
    fig.text(0.01, 0.93, "R² from regressing symmetric RCA in 2024 on 1989 across products",
             va="top", fontsize=8.5, color=MUTED)
    fig.text(0.01, 0.005, "*Japan's goods + services figure is not like for like (no Atlas services before 1996). "
             "Source: Harvard Growth Lab, Atlas of Economic Complexity.", fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.9))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main() -> None:
    df = rca.add_rca(rca.load_exports())
    res = results({"goods_and_services": df, "goods_only": goods_only(df)})
    res.round(4).to_csv(rca.OUT / "persistence_g7.csv", index=False)

    uk_scatter(df, rca.OUT / "uk_rca_1989_vs_2024.png")
    g7_scatter(df, res, rca.OUT / "g7_rca_1989_vs_2024.png")
    g7_bars(res, rca.OUT / "g7_persistence_r2.png")

    show = res.pivot_table(index="country_name", columns=["variant", "year"], values=["r2", "slope"]).round(2)
    print(show.to_string())


if __name__ == "__main__":
    main()
