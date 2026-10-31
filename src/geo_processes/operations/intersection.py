"""Planar intersection of bounded, valid two-dimensional CRS84 geometries."""

import json


def geometry_intersection(left, right):
    """Return GeoJSON, using an empty GeometryCollection for disjoint inputs.

    Coordinates are longitude/latitude; this is a planar GEOS operation, with
    no geodesic or antimeridian correction. Invalid topology is rejected.
    """
    from shapely.errors import GEOSException
    from shapely.geometry import mapping, shape

    def validate(geometry, depth=0, budget=None):
        budget = [10000] if budget is None else budget
        if not isinstance(geometry, dict) or depth > 8:
            raise ValueError("geometry must be a GeoJSON geometry with at most 8 collection levels")
        kind = geometry.get("type")
        if kind == "GeometryCollection":
            if set(geometry) != {"type", "geometries"} or not isinstance(geometry["geometries"], list):
                raise ValueError("GeometryCollection requires a geometries array")
            for member in geometry["geometries"]:
                validate(member, depth + 1, budget)
            return
        levels = {"Point": 0, "MultiPoint": 1, "LineString": 1, "MultiLineString": 2, "Polygon": 2, "MultiPolygon": 3}
        if kind not in levels or set(geometry) != {"type", "coordinates"}:
            raise ValueError("expected a GeoJSON geometry with type and coordinates")

        def coordinates(value, level):
            if not isinstance(value, list):
                raise ValueError("coordinates must be arrays")
            if level:
                for child in value:
                    coordinates(child, level - 1)
            elif value:
                budget[0] -= 1
                if (
                    budget[0] < 0
                    or len(value) != 2
                    or any(type(n) not in {int, float} for n in value)
                    or not -180 <= value[0] <= 180
                    or not -90 <= value[1] <= 90
                ):
                    raise ValueError("geometries require at most 10000 finite 2D CRS84 positions each")
            else:
                raise ValueError("empty positions are unsupported; use an empty GeometryCollection")

        coordinates(geometry["coordinates"], levels[kind])
        polygons = (
            [geometry["coordinates"]]
            if kind == "Polygon"
            else (geometry["coordinates"] if kind == "MultiPolygon" else [])
        )
        for polygon in polygons:
            for ring in polygon:
                if len(ring) < 4 or ring[0] != ring[-1]:
                    raise ValueError("polygon rings must be closed with at least four positions")

    validate(left)
    validate(right)
    try:
        first, second = shape(left), shape(right)
        if not first.is_valid or not second.is_valid:
            raise ValueError("input geometry has invalid topology")
        result = first.intersection(second)
        return (
            {"type": "GeometryCollection", "geometries": []}
            if result.is_empty
            else json.loads(json.dumps(mapping(result)))
        )
    except (GEOSException, TypeError, KeyError, IndexError) as error:
        raise ValueError("input geometry cannot be intersected") from error
