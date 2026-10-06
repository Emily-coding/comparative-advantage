"""Download the data used in the analysis. No API keys are needed.

* Atlas of Economic Complexity files come from the Harvard Growth Lab's
  Dataverse, the bulk download behind https://atlas.hks.harvard.edu/data-downloads.
* OECD-WTO BATIS comes from the OECD SDMX API.

Files are cached in data/raw/ and only downloaded once.
"""

from pathlib import Path

import requests

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
DATAVERSE = "https://dataverse.harvard.edu/api"
# Dataverse rejects the default python-requests user agent with a 403
HEADERS = {"User-Agent": "comparative-advantage/1.0 (+https://github.com/Emily-coding/comparative-advantage)"}

# (dataset DOI, file name in that dataset)
FILES = [
    # Goods exports by country x SITC Rev.2 2-digit division x year, 1962-2024
    ("doi:10.7910/DVN/H8SFD2", "sitc_country_product_year_2.csv"),
    # Services exports by country x broad services category x year, 1980-2024
    ("doi:10.7910/DVN/NDDMSN", "services_unilateral_country_product_year_2.csv"),
    # Product names for both classifications
    ("doi:10.7910/DVN/3BAL1O", "product_sitc.csv"),
    ("doi:10.7910/DVN/3BAL1O", "product_services_unilateral.csv"),
    # Country names (used to check the reporters are countries, not aggregates)
    ("doi:10.7910/DVN/3BAL1O", "location_country.csv"),
]


def file_ids(doi: str) -> dict[str, int]:
    """Map file name -> Dataverse file id for the latest version of a dataset."""
    r = requests.get(f"{DATAVERSE}/datasets/:persistentId/", params={"persistentId": doi}, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return {f["dataFile"]["filename"]: f["dataFile"]["id"] for f in r.json()["data"]["latestVersion"]["files"]}


# OECD-WTO Balanced Trade in Services: exports (X) to the world (W) by every
# reporter, EBOPS 2010 main components SA-SL plus total services (S), annual,
# current USD (exchange-rate converted), balanced values (B).
BATIS_URL = (
    "https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_BATIS@DF_BATIS,/"
    ".W.X..S+SA+SB+SC+SD+SE+SF+SG+SH+SI+SJ+SK+SL.A.USD_EXC.B"
)


def download_batis(out: Path) -> None:
    r = requests.get(
        BATIS_URL,
        params={"startPeriod": 2005, "endPeriod": 2024, "dimensionAtObservation": "AllDimensions"},
        headers=HEADERS | {"Accept": "application/vnd.sdmx.data+csv; charset=utf-8"},
        timeout=300,
    )
    r.raise_for_status()
    out.write_bytes(r.content)


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    ids_cache: dict[str, dict[str, int]] = {}
    for doi, name in FILES:
        out = RAW / name
        if out.exists():
            print(f"cached   {name}")
            continue
        if doi not in ids_cache:
            ids_cache[doi] = file_ids(doi)
        ids = ids_cache[doi]
        # format=original returns the CSV as uploaded rather than Dataverse's tab-separated copy
        url = f"{DATAVERSE}/access/datafile/{ids[name]}"
        # Write to a .part file and rename at the end, so an interrupted
        # download is never mistaken for a cached, complete file.
        tmp = out.with_suffix(".part")
        with requests.get(url, params={"format": "original"}, headers=HEADERS, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        tmp.replace(out)
        print(f"fetched  {name}")

    out = RAW / "batis_exports_world.csv"
    if out.exists():
        print(f"cached   {out.name}")
    else:
        download_batis(out)
        print(f"fetched  {out.name}")


if __name__ == "__main__":
    main()
