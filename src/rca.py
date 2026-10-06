"""Revealed comparative advantage (RCA) from the Atlas of Economic Complexity.

Replicates the method in Resolution Foundation, "Enduring strengths" (April
2022), Box 1 and Annex 1, and extends it to 2024:

* Goods: Atlas SITC Rev.2, 2-digit divisions.
* Services: Atlas "unilateral" services, 4 broad categories.
* Goods and services are pooled, so each country's total exports (and the
  world's) include both, and all products are ranked on one list.

RCA (Balassa) for country c and product p in year t:

    RCA = (X_cp / X_c) / (X_wp / X_w)

where X_c is c's total exports and w is the world, i.e. the sum over every
reporter in the Atlas (the Atlas files contain countries only, no regional
aggregates, so this does not double count).

The symmetric version used throughout the report maps RCA onto (-1, 1):

    RCA_sym = (RCA - 1) / (RCA + 1)

Values above 0 mean the country has a revealed comparative advantage.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs"

# Services start in 1980, so pooled goods+services RCAs start then too.
FIRST_YEAR = 1980
FOCUS_YEARS = [1989, 2019, 2024]
COUNTRY = "GBR"
TOP_N = 10

# Report Annex 1: dropped from the data entirely because of many missing flows
# across years. They are excluded from every total, including the world's.
DROP_FROM_DATA = {
    "91",  # Postal packages not classified according to kind
    "93",  # Special transactions, commodity not classified according to class
    "unspecified",  # Unspecified services
}

# Sensitivity check: in the current Atlas vintage much of the UK's business
# and professional services exports sit in "unspecified" (about $235bn in
# 2024), so dropping it from the data lowers the UK's total exports. This
# variant keeps it in every total but still keeps it out of the ranking.
DROP_FROM_DATA_SENSITIVITY = DROP_FROM_DATA - {"unspecified"}

# Report Figures 15/16 notes: kept in the data (so they count towards
# totals) but removed from the top-10 ranking as highly volatile.
DROP_FROM_RANKING = {
    "89",  # Miscellaneous manufactured articles, n.e.s.
    "96",  # Coin (other than gold coin), not being legal tender
    "97",  # Gold, non-monetary
}

# The Atlas now labels the "ict" category "Business services"; the report
# (using an earlier vintage) calls it "ICT". Keep the report's label so the
# lists can be compared by eye.
SERVICE_NAMES = {
    "financial": "Financial services",
    "ict": "ICT",
    "transport": "Transport",
    "travel": "Travel & tourism",
    "unspecified": "Unspecified services",
}


# BATIS services (EBOPS 2010 main components). SA-SL sum exactly to total
# services, so together they neither miss nor double count anything.
BATIS_NAMES = {
    "SA": "Manufacturing services on inputs owned by others",
    "SB": "Maintenance and repair services",
    "SC": "Transport",
    "SD": "Travel",
    "SE": "Construction",
    "SF": "Insurance and pension services",
    "SG": "Financial services",
    "SH": "Charges for the use of intellectual property",
    "SI": "Telecommunications, computer and information services",
    "SJ": "Other business services",
    "SK": "Personal, cultural and recreational services",
    "SL": "Government goods and services n.i.e.",
}
# BATIS reporters that are aggregates of other reporters. Excluding them leaves
# 200 individual economies whose sum equals BATIS's own world total exactly.
BATIS_AGGREGATES = {"W", "OECD", "EU27_2020"}
BATIS_FIRST_YEAR = 2005
# BATIS codes for former countries -> the code the Atlas files their goods under
# (the Atlas puts Serbia and Montenegro's goods under SRB). Kosovo (XKV) has
# no separate Atlas goods data, so it stays services-only.
BATIS_TO_ATLAS = {"ANT_F": "ANT", "SCG_F": "SRB"}


def load_atlas_services() -> pd.DataFrame:
    services = pd.read_csv(RAW / "services_unilateral_country_product_year_2.csv")
    return services.rename(columns={"country_iso3_code": "country", "product_services_unilateral_code": "product"})


def load_batis_services() -> pd.DataFrame:
    """BATIS exports to the world, by reporter x EBOPS main component x year."""
    b = pd.read_csv(RAW / "batis_exports_world.csv")
    b = b[b.SERVICE.isin(BATIS_NAMES) & ~b.REF_AREA.isin(BATIS_AGGREGATES)]
    assert (b.UNIT_MULT == 6).all(), "expected values in USD millions"
    return pd.DataFrame({
        "country": b.REF_AREA.replace(BATIS_TO_ATLAS),
        "year": b.TIME_PERIOD,
        "product": b.SERVICE,
        "export_value": b.OBS_VALUE * 1e6,  # USD millions -> USD, to match the Atlas
    })


def load_exports(drop_from_data: set[str] = DROP_FROM_DATA, services: str = "atlas") -> pd.DataFrame:
    """Long table of exports: country, year, product, product_name, sector, export_value.

    `drop_from_data` lists product codes removed before any totals are taken.
    `services` picks the services source: "atlas" (4 broad categories, from
    1980) or "batis" (12 EBOPS categories, from 2005). Goods always come from
    the Atlas SITC data.
    """
    goods = pd.read_csv(RAW / "sitc_country_product_year_2.csv", dtype={"product_sitc_code": str})
    goods = goods.rename(columns={"country_iso3_code": "country", "product_sitc_code": "product"})
    goods["sector"] = "goods"

    if services == "atlas":
        svc, first_year = load_atlas_services(), FIRST_YEAR
    elif services == "batis":
        svc, first_year = load_batis_services(), BATIS_FIRST_YEAR
    else:
        raise ValueError(f"unknown services source {services!r}")
    svc["sector"] = "services"

    cols = ["country", "year", "product", "sector", "export_value"]
    df = pd.concat([goods[cols], svc[cols]], ignore_index=True)
    df = df[(df.year >= first_year) & ~df["product"].isin(drop_from_data)]

    # Square the panel: every country x product x year, so a missing flow is
    # an explicit zero rather than an absent row.
    full = pd.MultiIndex.from_product(
        [df.country.unique(), df.year.unique(), df["product"].unique()],
        names=["country", "year", "product"],
    )
    sector = df.drop_duplicates("product").set_index("product")["sector"]
    df = df.set_index(["country", "year", "product"])[["export_value"]].reindex(full).reset_index()
    df["sector"] = df["product"].map(sector)

    # Missing and negative flows -> 0. Negatives occur in a few services
    # series (e.g. insurance claims exceeding premiums in a year). A country
    # reporting goods but not services (or vice versa) gets zeros for the
    # missing side, which leaves the world totals unchanged.
    df["export_value"] = df["export_value"].fillna(0).clip(lower=0)

    names = pd.read_csv(RAW / "product_sitc.csv", dtype={"product_sitc_code": str})
    names = names[names.product_level == 2].set_index("product_sitc_code")["product_name_short"]
    df["product_name"] = df["product"].map(names).fillna(df["product"].map(SERVICE_NAMES | BATIS_NAMES))
    assert df["product_name"].notna().all(), "unnamed product code"
    return df


def add_rca(df: pd.DataFrame) -> pd.DataFrame:
    """Add Balassa RCA and its symmetric (-1, 1) transform."""
    country_total = df.groupby(["country", "year"]).export_value.transform("sum")
    world_product = df.groupby(["year", "product"]).export_value.transform("sum")
    world_total = df.groupby("year").export_value.transform("sum")

    df["share_of_country_exports"] = df.export_value / country_total
    df["share_of_world_exports"] = world_product / world_total
    df["rca"] = df.share_of_country_exports / df.share_of_world_exports
    df["rca_sym"] = (df.rca - 1) / (df.rca + 1)

    # A country with no recorded exports at all in a year has no defined RCA.
    return df[country_total > 0].copy()


def top_n(df: pd.DataFrame, country: str, year: int, n: int = TOP_N) -> pd.DataFrame:
    """A country's n highest-RCA products in a year, excluding the volatile ones."""
    excluded = DROP_FROM_RANKING | {"unspecified"}  # only present in the sensitivity variant
    d = df[(df.country == country) & (df.year == year) & ~df["product"].isin(excluded)]
    d = d.sort_values("rca_sym", ascending=False).head(n)
    return d.assign(rank=range(1, len(d) + 1))
