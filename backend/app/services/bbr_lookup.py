"""
BBR building lookup, chained through DAWA.

Chain: address text -> DAWA (husnummer ID) -> BBR GraphQL (building details)

An address can have multiple BBR_Bygning records (main building plus
outbuildings/technical structures). We pick the one with the most
complete data (non-null construction year) as the "main" building.
"""

import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

from app.services.dawa_lookup import resolve_address

DATAFORDELER_API_KEY = os.getenv("DATAFORDELER_API_KEY")
BBR_GRAPHQL_URL = "https://graphql.datafordeler.dk/BBR/v3"

# Placeholder mapping — BBR's official use-code list (kodeliste) has 
# dozens of codes; expand this as needed. 
# https://danmarksadresser.dk/adressedata/kodelister for the full list.
USE_CODE_TO_BUILDING_TYPE = {
    "120": "detached",       # Fritliggende enfamiliehus
    "121": "detached",       # Sammenbygget enfamiliehus (row house, treated as detached-ish for now)
    "140": "apartment",      # Etagebolig, flerfamiliehus
    "321": "public",         # Bygning til kontor, handel, offentlig administration mv.
}


def get_bbr_building(address_text: str):
    address = resolve_address(address_text)
    if address is None:
        return {"error": f"Address '{address_text}' not found in DAWA"}

    husnummer_id = address["raw"]["adgangsadresse"]["id"]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    query = """
    query GetBuilding($husnummer: String!, $time: DafDateTime!) {
      BBR_Bygning(
        virkningstid: $time,
        registreringstid: $time,
        where: { husnummer: { eq: $husnummer } }
      ) {
        nodes {
          byg026Opfoerelsesaar
          byg054AntalEtager
          byg021BygningensAnvendelse
          id_lokalId
          husnummer
        }
      }
    }
    """

    response = requests.post(
        f"{BBR_GRAPHQL_URL}?apikey={DATAFORDELER_API_KEY}",
        json={
            "query": query,
            "variables": {"husnummer": husnummer_id, "time": now},
        },
    )
    response.raise_for_status()
    result = response.json()

    nodes = result.get("data", {}).get("BBR_Bygning", {}).get("nodes", [])

    # Pick the building with the most complete data (has a construction year)
    candidates = [n for n in nodes if n.get("byg026Opfoerelsesaar") is not None]
    main_building = candidates[0] if candidates else (nodes[0] if nodes else None)

    if main_building is None:
        return {"error": "No BBR building record found for this address"}

    use_code = main_building.get("byg021BygningensAnvendelse")

    return {
        "address_text": address["address_text"],
        "latitude": address["latitude"],
        "longitude": address["longitude"],
        "building_age": main_building.get("byg026Opfoerelsesaar"),
        "floor_count": main_building.get("byg054AntalEtager"),
        "building_use_code": use_code,
        "building_type": USE_CODE_TO_BUILDING_TYPE.get(use_code, "unknown"),
        "bbr_id": main_building.get("id_lokalId"),
    }


if __name__ == "__main__":
    result = get_bbr_building("Rådhuspladsen 1, København")
    print(result)