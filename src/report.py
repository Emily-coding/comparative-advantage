"""Build the outputs: RCA tables, the UK top-10 comparison and charts.

Run after download.py:  python src/report.py
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import rca

# Published UK top-10 lists from Resolution Foundation, "Enduring strengths"
# (2022), Figures 15 and 16 (page 34), mapped to product codes. The figures
# give the lists only (legends are alphabetical), not the order within them,
# except that the text says financial services and beverages were the top two
# in both years.
PUBLISHED = {
    1989: ["financial", "11", "59", "53", "87", "54", "75", "79", "55", "71"],
    2019: ["41", "11", "53", "financial", "ict", "54", "79", "55", "71", "transport"],
}
PUBLISHED_TOP_TWO = {"financial", "11"}
BATIS_YEARS = [2005, 2019, 2024]

# Categorical slots 1-3 of the reference palette (validated all-pairs).
YEAR_COLOURS = {1989: "#2a78d6", 2019: "#eb6834", 2024: "#1baf7a"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def overlap(a: list[str], b: list[str]) -> list[str]:
    return [p for p in a if p in b]


def comparison_lines(df: pd.DataFrame, names: dict[str, str], label: str) -> list[str]:
    """Markdown answering the report's claim for one data variant."""
    rec = {y: rca.top_n(df, rca.COUNTRY, y)["product"].tolist() for y in rca.FOCUS_YEARS}
    nm = lambda codes: ", ".join(names[c] for c in codes) or "none"

    lines = [f"## {label}", ""]
    lines += ["### Recomputed UK top 10", ""]
    table = pd.DataFrame({y: [names[c] for c in rec[y]] for y in rca.FOCUS_YEARS}, index=range(1, 11))
    lines += [table.rename_axis("Rank").to_markdown(), ""]

    lines += ["### Is the claim still true in 2024?", ""]
    for base_label, base_1989, top_two in [
        ("Published 1989 list", PUBLISHED[1989], PUBLISHED_TOP_TWO),
        ("Recomputed 1989 list", rec[1989], set(rec[1989][:2])),
    ]:
        kept = overlap(base_1989, rec[2024])
        dropped = [c for c in base_1989 if c not in rec[2024]]
        top_two_now = set(rec[2024][:2])
        lines += [
            f"**Against the {base_label.lower()}:**",
            "",
            f"- {len(kept)} of the 10 are in the 2024 top 10 (the report found 7 for 2019).",
            f"- Still in: {nm(kept)}.",
            f"- Dropped out: {nm(dropped)}.",
            f"- Top two in 1989: {nm(sorted(top_two))}. Top two in 2024: {nm(rec[2024][:2])}. "
            f"Same pair: **{'yes' if top_two == top_two_now else 'no'}**.",
            "",
        ]

    kept_19 = overlap(PUBLISHED[2019], rec[2019])
    lines += [
        "### How close is the recomputed 2019 list to the published one?",
        "",
        f"- {len(kept_19)} of the 10 published 2019 products are in the recomputed 2019 top 10.",
        f"- Published but not recomputed: {nm([c for c in PUBLISHED[2019] if c not in rec[2019]])}.",
        f"- Recomputed but not published: {nm([c for c in rec[2019] if c not in PUBLISHED[2019]])}.",
        "",
    ]
    return lines


# The Atlas services categories in the report's lists, mapped to BATIS. The
# Atlas "financial" category covers insurance and finance, so it counts as in
# the top 10 if either BATIS category is.
ATLAS_TO_BATIS = {"financial": {"SF", "SG"}, "ict": {"SI"}, "transport": {"SC"}}


def batis_lines(df: pd.DataFrame, atlas_df: pd.DataFrame, names: dict[str, str]) -> list[str]:
    """Markdown for the Atlas goods + BATIS services comparison."""
    rec = {y: rca.top_n(df, rca.COUNTRY, y)["product"].tolist() for y in BATIS_YEARS}
    nm = lambda codes: ", ".join(names[c] for c in codes) or "none"

    lines = ["## Comparison: Atlas goods + BATIS services (12 categories, 2005–2024)", ""]
    lines += ["BATIS starts in 2005, so this version cannot go back to 1989.", ""]
    lines += ["### UK top 10", ""]
    table = pd.DataFrame({y: [names[c] for c in rec[y]] for y in BATIS_YEARS}, index=range(1, 11))
    lines += [table.rename_axis("Rank").to_markdown(), ""]
    lines += [f"- Services in the 2024 top 10: {sum(c in rca.BATIS_NAMES for c in rec[2024])} of 10 "
              f"(Atlas-only version: {sum(not c.isdigit() for c in rca.top_n(atlas_df, rca.COUNTRY, 2024)['product'])} of 10).", ""]

    lines += ["### Persistence", ""]
    for start in BATIS_YEARS[:-1]:
        kept = overlap(rec[start], rec[2024])
        lines += [f"- {start} → 2024: {len(kept)} of 10 still in the top 10. "
                  f"Top two {nm(rec[start][:2])} → {nm(rec[2024][:2])}."]
    in_2024 = set(rec[2024])
    hits = [c for c in PUBLISHED[1989] if ATLAS_TO_BATIS.get(c, {c}) & in_2024]
    lines += [
        f"- Published 1989 list: {len(hits)} of 10 are in this 2024 top 10 "
        f"(financial services counts if either BATIS insurance or financial services is in). "
        f"Still in: {nm(hits)}.",
        "",
    ]
    return lines


def dot_plot(df: pd.DataFrame, path, years: list[int], products: set[str], title: str, source: str) -> None:
    """Symmetric RCA in three years for a set of products, one row per product."""
    uk = df[df.country == rca.COUNTRY]
    wide = (
        uk[uk["product"].isin(products) & uk.year.isin(years)]
        .pivot_table(index="product_name", columns="year", values="rca_sym")
        .sort_values(years[-1])
    )

    fig, ax = plt.subplots(figsize=(9, 0.42 * len(wide) + 1.8))
    ax.axvline(0, color=MUTED, lw=1)
    for i, (_, row) in enumerate(wide.iterrows()):
        ax.plot([row.min(), row.max()], [i, i], color=GRID, lw=2, zorder=1)
    # Colours follow slot order (first year = slot 1). Small vertical offsets
    # stop near-identical years hiding each other.
    for y, colour, dy in zip(years, YEAR_COLOURS.values(), (-0.18, 0, 0.18)):
        ax.scatter(wide[y], [i + dy for i in range(len(wide))], s=46, color=colour,
                   edgecolor="white", linewidth=1.5, zorder=3, label=str(y))
    ax.set_yticks(range(len(wide)), wide.index, fontsize=9, color=INK)
    ax.set_xlim(-1, 1)
    ax.set_xlabel("Symmetric RCA  (>0 = UK has a revealed comparative advantage)", color=MUTED, fontsize=9)
    fig.text(0.01, 0.985, title, va="top", fontsize=12, color=INK)
    fig.text(0.01, 0.95, f"Every product in any top-10 list shown, sorted by {years[-1]}",
             va="top", fontsize=8.5, color=MUTED)
    ax.legend(loc="lower right", frameon=False, fontsize=9, reverse=True)
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=MUTED, length=0)
    fig.text(0.01, 0.005, f"Source: {source}.", fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 0.93))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def small_multiples(df: pd.DataFrame, path) -> None:
    """RCA over time, one panel per product in the published 1989 top 10.

    Starts in 1989, like the report's Figure 15: before 1986 the Atlas has no
    UK financial services exports, which would show as a spurious -1.
    """
    uk = df[(df.country == rca.COUNTRY) & (df.year >= 1989)]
    order = rca.top_n(df, rca.COUNTRY, 1989)["product"].tolist()
    order = PUBLISHED[1989] + [p for p in order if p not in PUBLISHED[1989]]
    cols = 4
    rows = -(-len(order) // cols)
    fig, axes = plt.subplots(rows, cols, figsize=(12, 2.3 * rows), sharex=True, sharey=True)
    for ax, p in zip(axes.flat, order):
        s = uk[uk["product"] == p].sort_values("year")
        ax.axhline(0, color=MUTED, lw=0.8)
        ax.plot(s.year, s.rca_sym, color=YEAR_COLOURS[1989], lw=2)
        for y, colour in YEAR_COLOURS.items():
            v = s.loc[s.year == y, "rca_sym"]
            ax.scatter([y], v, s=30, color=colour, edgecolor="white", linewidth=1.2, zorder=3)
        name = s.product_name.iloc[0]
        flag = "" if p in PUBLISHED[1989] else "  (recomputed 1989 only)"
        ax.set_title((name[:38] + "…" if len(name) > 39 else name) + flag, fontsize=8.5, loc="left", color=INK)
        ax.set_ylim(-1, 1)
        ax.grid(axis="y", color=GRID, lw=0.6)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.tick_params(colors=MUTED, labelsize=8, length=0)
    for ax in list(axes.flat)[len(order):]:
        ax.set_visible(False)
    fig.suptitle("UK symmetric RCA, 1989–2024: products in the 1989 top 10", x=0.01, ha="left", fontsize=12, color=INK)
    fig.text(0.01, 0.005, "Dots mark 1989 (blue), 2019 (orange) and 2024 (green). Source: Harvard Growth Lab, Atlas of Economic Complexity.",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main() -> None:
    rca.OUT.mkdir(exist_ok=True)
    main_df = rca.add_rca(rca.load_exports())
    sens_df = rca.add_rca(rca.load_exports(rca.DROP_FROM_DATA_SENSITIVITY))
    batis_df = rca.add_rca(rca.load_exports(services="batis"))
    names = main_df.drop_duplicates("product").set_index("product")["product_name"].to_dict()
    for d in (sens_df, batis_df):
        names |= d.drop_duplicates("product").set_index("product")["product_name"].to_dict()

    cols = ["country", "year", "sector", "product", "product_name", "export_value",
            "share_of_country_exports", "share_of_world_exports", "rca", "rca_sym"]
    main_df[main_df.year.isin(rca.FOCUS_YEARS)][cols].sort_values(cols[:4]).to_csv(
        rca.OUT / "rca_all_countries_1989_2019_2024.csv", index=False)
    main_df[main_df.country == rca.COUNTRY][cols].sort_values(["year", "product"]).to_csv(
        rca.OUT / "rca_uk_1980_2024.csv", index=False)
    batis_df[batis_df.year.isin(BATIS_YEARS)][cols].sort_values(cols[:4]).to_csv(
        rca.OUT / "rca_batis_all_countries_2005_2019_2024.csv", index=False)

    tops = []
    for variant, df, years in [("main", main_df, rca.FOCUS_YEARS),
                               ("sensitivity_keep_unspecified", sens_df, rca.FOCUS_YEARS),
                               ("batis_services", batis_df, BATIS_YEARS)]:
        for y in years:
            t = rca.top_n(df, rca.COUNTRY, y)
            tops.append(t.assign(variant=variant, source="recomputed")[
                ["variant", "source", "year", "rank", "product", "product_name", "rca", "rca_sym"]])
    for y, codes in PUBLISHED.items():
        tops.append(pd.DataFrame({"variant": "", "source": "published", "year": y, "rank": None,
                                  "product": codes, "product_name": [names[c] for c in codes]}))
    pd.concat(tops).to_csv(rca.OUT / "uk_top10.csv", index=False)

    md = ["# UK top-10 revealed comparative advantage: 1989, 2019 and 2024", ""]
    md += ["Published lists: Resolution Foundation, *Enduring strengths* (2022), Figures 15 and 16.", ""]
    md += comparison_lines(main_df, names, "Main results (the report's drops)")
    md += comparison_lines(sens_df, names,
                           "Sensitivity check: \"unspecified\" services kept in the totals (still excluded from the ranking)")
    md += batis_lines(batis_df, main_df, names)
    (rca.OUT / "uk_top10_comparison.md").write_text("\n".join(md))

    atlas_products = set(PUBLISHED[1989]) | set(PUBLISHED[2019])
    for y in rca.FOCUS_YEARS:
        atlas_products |= set(rca.top_n(main_df, rca.COUNTRY, y)["product"])
    dot_plot(main_df, rca.OUT / "uk_rca_dot_plot.png", rca.FOCUS_YEARS, atlas_products,
             "UK revealed comparative advantage: 1989, 2019 and 2024",
             "Harvard Growth Lab, Atlas of Economic Complexity (SITC Rev.2 goods + services)")
    batis_products = set().union(*(rca.top_n(batis_df, rca.COUNTRY, y)["product"] for y in BATIS_YEARS))
    dot_plot(batis_df, rca.OUT / "uk_rca_dot_plot_batis.png", BATIS_YEARS, batis_products,
             "UK revealed comparative advantage with BATIS services: 2005, 2019 and 2024",
             "Harvard Growth Lab, Atlas of Economic Complexity (SITC Rev.2 goods); OECD-WTO BATIS (services)")
    small_multiples(main_df, rca.OUT / "uk_rca_1989_top10_over_time.png")
    print("\n".join(md))


if __name__ == "__main__":
    main()
