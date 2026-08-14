"""
DAWA (Danmarks Adresser Web API) integration.

Free, no authentication required. Resolves a typed Danish address
into coordinates and a linked BBR building ID, which is needed
before BBR_Bygning can be queried (BBR's GraphQL API requires an
internal building ID, not an address, to look up a building).
"""

import requests

DAWA_BASE_URL = "https://api.dataforsyningen.dk"


def search_address(query: str, limit: int = 5):
    """
    Free-text address search/autocomplete.
    Returns a list of candidate matches.
    """
    response = requests.get(
        f"{DAWA_BASE_URL}/adresser/autocomplete",
        params={"q": query, "per_side": limit},
    )
    response.raise_for_status()
    return response.json()


def get_address_details(address_id: str):
    """
    Given a specific DAWA address ID, return full details including
    coordinates and (if available) the linked BBR building ID.
    """
    response = requests.get(f"{DAWA_BASE_URL}/adresser/{address_id}")
    response.raise_for_status()
    return response.json()


def resolve_address(query: str):
    """
    Convenience function: takes a free-text address string,
    returns the best match's coordinates and identifiers.
    """
    candidates = search_address(query, limit=1)
    if not candidates:
        return None

    best_match = candidates[0]
    address_id = best_match["adresse"]["id"]

    details = get_address_details(address_id)

    return {
        "address_text": details.get("adressebetegnelse"),
        "latitude": details["adgangsadresse"]["adgangspunkt"]["koordinater"][1],
        "longitude": details["adgangsadresse"]["adgangspunkt"]["koordinater"][0],
        "kommunekode": details["adgangsadresse"]["kommune"]["kode"],
        "raw": details,  # keep full response around for finding BBR linkage fields
    }


if __name__ == "__main__":
    result = resolve_address("Rådhuspladsen 1, København")
    print(result)