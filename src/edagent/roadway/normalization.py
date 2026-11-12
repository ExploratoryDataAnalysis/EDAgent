"""Roadway reference normalization engine.

Standardizes street names, USPS Pub 28 suffixes, directional tokens, state routes,
and road classifications to enable reproducible matching.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from edagent.roadway.schema import RoadClass

# USPS Publication 28 standard suffix abbreviations
STREET_SUFFIX_MAP = {
    "ALLEY": "ALY",
    "ALLY": "ALY",
    "ALY": "ALY",
    "AVENUE": "AVE",
    "AV": "AVE",
    "AVE": "AVE",
    "AVEN": "AVE",
    "BOULEVARD": "BLVD",
    "BLVD": "BLVD",
    "BOUL": "BLVD",
    "CIRCLE": "CIR",
    "CIR": "CIR",
    "CIRC": "CIR",
    "COURT": "CT",
    "CT": "CT",
    "DRIVE": "DR",
    "DR": "DR",
    "DRIV": "DR",
    "EXPRESSWAY": "EXPWY",
    "EXPWY": "EXPWY",
    "EXPR": "EXPWY",
    "FREEWAY": "FWY",
    "FWY": "FWY",
    "HIGHWAY": "HWY",
    "HWY": "HWY",
    "HIGHWY": "HWY",
    "LANE": "LN",
    "LN": "LN",
    "PARKWAY": "PKWY",
    "PKWY": "PKWY",
    "PKY": "PKWY",
    "PLACE": "PL",
    "PL": "PL",
    "PLAZA": "PLZ",
    "PLZ": "PLZ",
    "ROAD": "RD",
    "RD": "RD",
    "STREET": "ST",
    "ST": "ST",
    "STR": "ST",
    "TERRACE": "TER",
    "TER": "TER",
    "TRAIL": "TRL",
    "TRL": "TRL",
    "TR": "TRL",
    "WAY": "WAY",
    "WY": "WAY",
    "PIKE": "PIKE",
    "TURNPIKE": "TPKE",
    "TPKE": "TPKE",
    "RAMP": "RAMP",
    "EXTENSION": "EXT",
    "EXT": "EXT",
    "CONNECTOR": "CONN",
    "CONN": "CONN",
}

# Directional tokens
DIRECTIONAL_MAP = {
    "NORTH": "N",
    "SOUTH": "S",
    "EAST": "E",
    "WEST": "W",
    "NORTHEAST": "NE",
    "NORTHWEST": "NW",
    "SOUTHEAST": "SE",
    "SOUTHWEST": "SW",
    "N": "N",
    "S": "S",
    "E": "E",
    "W": "W",
    "NE": "NE",
    "NW": "NW",
    "SE": "SE",
    "SW": "SW",
}


def normalize_street_name(raw_name: Optional[str]) -> str:
    """Normalize a street name string following USPS Publication 28 standards.

    Applies:
    - Uppercase conversion
    - Stripping punctuation and excess whitespace
    - Directional abbreviation (NORTH -> N)
    - Street type suffix standardization (STREET -> ST, AVENUE -> AVE)
    - Removal of trailing duplicate suffixes (e.g. 'MAIN ST ST' -> 'MAIN ST')
    """
    if not raw_name:
        return ""

    text = str(raw_name).strip().upper()

    # Replace hyphens, slashes, and periods with spaces, except within recognized route codes
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = [t for t in re.split(r"\s+", text) if t]

    if not tokens:
        return ""

    # Normalize directional prefix if present
    if len(tokens) > 1 and tokens[0] in DIRECTIONAL_MAP:
        tokens[0] = DIRECTIONAL_MAP[tokens[0]]

    # Normalize directional suffix if present at end
    if len(tokens) > 1 and tokens[-1] in DIRECTIONAL_MAP:
        tokens[-1] = DIRECTIONAL_MAP[tokens[-1]]

    # Normalize street type suffixes occurring near the end
    for i in range(len(tokens)):
        if tokens[i] in STREET_SUFFIX_MAP and (i >= len(tokens) - 2):
            tokens[i] = STREET_SUFFIX_MAP[tokens[i]]

    # Remove trailing duplicate suffixes (e.g. ['MAIN', 'ST', 'ST'] -> ['MAIN', 'ST'])
    while (
        len(tokens) >= 2
        and tokens[-1] in STREET_SUFFIX_MAP.values()
        and tokens[-2] in STREET_SUFFIX_MAP.values()
        and tokens[-1] == tokens[-2]
    ):
        tokens.pop()

    return " ".join(tokens)


def normalize_route_number(raw_route: Optional[str]) -> Optional[str]:
    """Normalize state route identifiers to 4-digit zero-padded numbers.

    Examples:
    - '22' -> '0022'
    - 'SR 28' -> '0028'
    - 'I-376' -> '0376'
    - '376' -> '0376'
    - '8001' -> '8001'
    """
    if not raw_route:
        return None

    cleaned = str(raw_route).strip().upper()
    digits = re.findall(r"\d+", cleaned)
    if not digits:
        return None

    num = int(digits[0])
    if 1 <= num <= 9999:
        return f"{num:04d}"

    return None


def parse_intersection_streets(raw_str: Optional[str]) -> List[str]:
    """Split and normalize intersecting streets from a composite junction string.

    Supports separators: '&', '/', ' AT ', ' AND ', ';'.
    Returns deduplicated, sorted normalized street names.
    """
    if not raw_str:
        return []

    text = str(raw_str).strip().upper()
    parts = re.split(r"\s*(?:&|/|\bAT\b|\bAND\b|;)\s*", text)

    normalized_parts = []
    for p in parts:
        norm = normalize_street_name(p)
        if norm and norm not in normalized_parts:
            normalized_parts.append(norm)

    # Sort alphabetically to guarantee order invariance (A & B == B & A)
    normalized_parts.sort()
    return normalized_parts


def map_road_class(
    road_owner: Optional[Any] = None,
    fcc: Optional[str] = None,
    route: Optional[str] = None,
    lar: Optional[str] = None,
) -> RoadClass:
    """Map PennDOT ownership codes and County FCC attributes to normalized RoadClass."""
    # 1. State Route inspection
    route_num = normalize_route_number(route)
    if route_num:
        num = int(route_num)
        if num in {76, 79, 279, 376, 576, 579}:
            return RoadClass.INTERSTATE
        if 8001 <= num <= 8999:
            return RoadClass.RAMP
        return RoadClass.STATE_ROUTE

    # 2. Check PennDOT ROAD_OWNER code
    if road_owner is not None:
        try:
            owner_code = int(float(road_owner))
            if owner_code in {1, 5, 6}:
                return RoadClass.INTERSTATE
            if owner_code == 2:
                return RoadClass.STATE_ROUTE
            if owner_code == 3:
                return RoadClass.COUNTY_ROAD
            if owner_code in {4, 7}:
                return RoadClass.LOCAL_STREET
        except (ValueError, TypeError):
            pass

    # 3. Check County Centerline FCC (Feature Class Code)
    if fcc:
        fcc_clean = str(fcc).strip().upper()
        if fcc_clean.startswith("A1") or (lar and str(lar).strip().upper() == "Y"):
            return RoadClass.INTERSTATE
        if fcc_clean.startswith("A2"):
            return RoadClass.STATE_ROUTE
        if fcc_clean.startswith("A3"):
            return RoadClass.COUNTY_ROAD
        if fcc_clean.startswith("A4"):
            return RoadClass.LOCAL_STREET
        if fcc_clean in {"A63", "A64", "A65"}:
            return RoadClass.RAMP

    return RoadClass.LOCAL_STREET
