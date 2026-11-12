"""Evidence for reviewing changes and junctions in projected centerline snapshots."""

from collections import defaultdict
from math import isfinite

from shapely.geometry import Point
from shapely.strtree import STRtree


def match_reviewed_site(point, candidates, *, when, road_class, direction, site_type,
                        coordinate_quality, lrs_site_ids, acceptance_m, tie_m, metres_per_unit):
    """Evaluate a scoped, independently reviewed candidate set in a projected CRS."""
    if (not all(isfinite(n) for n in (acceptance_m, tie_m, metres_per_unit))
            or not 0 < metres_per_unit or not 0 <= tie_m < acceptance_m):
        raise ValueError("Invalid matching policy distances")
    if coordinate_quality == "CONFLICT":
        return "AMBIGUOUS", None, "COORDINATE_CONFLICT", []
    if coordinate_quality != "VERIFIED" or point is None:
        return "UNMATCHED", None, "COORDINATES_UNVERIFIED", []
    evidence = []
    for site in candidates:
        distance = point.distance(site["geometry"]) * metres_per_unit
        reason = "ELIGIBLE"
        if not site["valid_from"] <= when <= site["valid_through"]:
            reason = "OUTSIDE_EFFECTIVE_DATES"
        elif site["road_class"] != road_class or site["site_type"] != site_type:
            reason = "INCOMPATIBLE_ROAD_OR_SITE_TYPE"
        elif direction and direction not in site["directions"]:
            reason = "INCOMPATIBLE_OR_UNKNOWN_DIRECTION"
        elif site_type == "INTERSECTION" and not site.get("at_grade_evidence"):
            reason = "AT_GRADE_UNVERIFIED"
        elif distance > acceptance_m:
            reason = "OUTSIDE_ACCEPTANCE_DISTANCE"
        evidence.append((distance, site["site_id"], reason))
    evidence.sort()
    eligible = [(distance, site_id) for distance, site_id, reason in evidence if reason == "ELIGIBLE"]
    if lrs_site_ids is not None:
        corroborated = [row for row in eligible if row[1] in lrs_site_ids]
        if len(lrs_site_ids) != 1 or not corroborated:
            return "AMBIGUOUS", None, "LRS_GEOMETRY_DISAGREE_OR_UNRESOLVED", evidence
        return "MATCHED", corroborated[0][1], "INDEPENDENT_LRS_AND_GEOMETRY", evidence
    if not eligible:
        return "UNMATCHED", None, "NO_ELIGIBLE_SITE", evidence
    if len(eligible) > 1 and eligible[1][0] - eligible[0][0] <= tie_m:
        return "AMBIGUOUS", None, "GEOMETRY_TIE", evidence
    return "MATCHED", eligible[0][1], "REVIEWED_GEOMETRY", evidence


def line_edges(line):
    parts = line.geoms if line.geom_type == "MultiLineString" else [line]
    edges = set()
    for part in parts:
        for a, b in zip(part.coords, list(part.coords)[1:]):
            edge = tuple(sorted((a[:2], b[:2])))
            if edge[0] != edge[1]:
                edges.add(edge)
    return frozenset(edges)


def segment_lineage(older, newer):
    """Link identical edges, preserving only unique one-to-one geometry continuity."""
    edge_index = defaultdict(set)
    for key, (_, edges) in newer.items():
        for edge in edges:
            edge_index[edge].add(key)
    forward = {}
    reverse = defaultdict(set)
    for key, (_, edges) in older.items():
        neighbors = set().union(*(edge_index[edge] for edge in edges if edge in edge_index))
        if key in newer:
            neighbors.add(key)
        forward[key] = neighbors
        for neighbor in neighbors:
            reverse[neighbor].add(key)

    for key, neighbors in sorted(forward.items()):
        if not neighbors:
            yield key, "", "UNRESOLVED_NO_EDGE_OR_KEY"
        name, edges = older[key]
        for neighbor in sorted(neighbors):
            new_name, new_edges = newer[neighbor]
            evidence = "UNRESOLVED_CHANGED_GEOMETRY_OR_NAME"
            if (len(neighbors) == 1 and len(reverse[neighbor]) == 1 and edges
                    and edges == new_edges and name == new_name):
                evidence = "IDENTICAL" if key == neighbor else "RENUMBERING_CANDIDATE"
            elif len(neighbors) > 1 and len(reverse[neighbor]) == 1 and new_edges < edges:
                evidence = "SPLIT_CANDIDATE"
            elif len(reverse[neighbor]) > 1 and len(neighbors) == 1 and edges < new_edges:
                evidence = "MERGE_CANDIDATE"
            yield key, neighbor, evidence
    for key in sorted(newer.keys() - reverse.keys()):
        yield "", key, "UNRESOLVED_NO_PREDECESSOR"


def cluster_junctions(nodes, sites, maximum_distance):
    """Group nearby endpoint nodes sharing a road pair or a connecting ramp.

    Require pairwise agreement to keep a chain of nearby nodes from collapsing
    several intersections. Membership alone supplies no grade evidence.
    """
    points = [Point(node["x"], node["y"]) for node in nodes]
    tree = STRtree(points)
    groups = []
    assigned = {}
    for index, node in enumerate(nodes):
        neighbors = set()
        for neighbor in tree.query(points[index], predicate="dwithin", distance=maximum_distance):
            if neighbor >= index:
                continue
            other = nodes[neighbor]
            shared = node["segments"] & other["segments"]
            if len(node["roads"] & other["roads"]) >= 2 or any(sites[s]["ramp"] for s in shared):
                neighbors.add(neighbor)
        for group_id in sorted({assigned[n] for n in neighbors}):
            if all(member in neighbors for member in groups[group_id]):
                groups[group_id].append(index)
                assigned[index] = group_id
                break
        else:
            assigned[index] = len(groups)
            groups.append([index])
    return groups
