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

# Confirmed against BBR's official kodeliste (ki.bbr.dk/kodelister-i-bbr/0/1/0/YdervaeggenesMateriale)
WALL_MATERIAL_HEAT_RISK = {
    "1": "low",      # Mursten (brick) - good thermal mass
    "2": "medium",   # Letbetonsten (lightweight concrete)
    "3": "medium",   # Fibercement inkl. asbest
    "4": "high",     # Bindingsværk (timber frame) - less thermal mass
    "5": "high",     # Træ (wood)
    "6": "medium",   # Betonelementer (concrete elements)
    "8": "high",     # Metal - poor insulation, absorbs heat
    "10": "medium",  # Fibercement uden asbest
    "11": "high",    # Plastmaterialer (plastic)
    "12": "high",    # Glas (glass) - significant heat gain
    "80": "unknown", # Ingen (none registered)
    "90": "unknown", # Andet materiale (other)
}

# Confirmed against BBR's official kodeliste (field 212, Tagdaekningsmateriale)
ROOF_MATERIAL_HEAT_RISK = {
    "1": "high",     # Built-up (flat roof) - typically dark, absorbs heat, poor ventilation
    "2": "high",     # Tagpap (roofing felt) - dark, absorbs heat
    "3": "medium",   # Fibercement inkl. asbest
    "4": "medium",   # Cementsten (concrete tiles)
    "5": "low",      # Tegl (clay tile) - lighter colored, better heat reflection, ventilated
    "6": "high",     # Metalplader (metal sheets) - poor insulation, absorbs/conducts heat
    "7": "low",      # Stråtag (thatch) - excellent natural insulation
    "10": "medium",  # Fibercement asbestfri
    "11": "high",    # PVC - poor thermal performance
    "12": "high",    # Glas (glass) - significant heat gain
    "90": "unknown", # Andet (other) - genuinely unknown
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
          byg032YdervaeggensMateriale
          byg033Tagdaekningsmateriale
          byg111StormraadetsOversvoemmelsesSelvrisiko
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
        "wall_material_code": main_building.get("byg032YdervaeggensMateriale"),
        "roof_material_code": main_building.get("byg033Tagdaekningsmateriale"),
        "wall_heat_risk": WALL_MATERIAL_HEAT_RISK.get(
            main_building.get("byg032YdervaeggensMateriale"), "unknown"
        ),
        "roof_heat_risk": ROOF_MATERIAL_HEAT_RISK.get(
            main_building.get("byg033Tagdaekningsmateriale"), "unknown"
        ),
        "stormraad_flood_risk": main_building.get("byg111StormraadetsOversvoemmelsesSelvrisiko"),
        "bbr_id": main_building.get("id_lokalId"),
    }


if __name__ == "__main__":
    result = get_bbr_building("Rådhuspladsen 1, København")
    print(result)