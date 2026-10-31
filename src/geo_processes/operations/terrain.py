"""Terrain-only extraction of the user-supplied ingestion/sync_terrain.py.

The algorithm below is preserved. See examples/contributor-experience/REPORT.md
for provenance, extraction changes and known algorithm/runtime limitations.
Import this module during execution, not metadata discovery.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path

import pyproj
import requests
from requests import RequestException
from shapely.geometry import Point, shape
from shapely.ops import transform, unary_union
from shapely.validation import make_valid

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
ALKMAAR_POLYGON_FILE = BASE_DIR.parent / "data" / "terrain" / "gemeente_alkmaar.geojson"

# Define global transformers
try:
    to_rd = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:28992", always_xy=True).transform
    to_wgs = pyproj.Transformer.from_crs("EPSG:28992", "EPSG:4326", always_xy=True).transform
except Exception as e:
    logger.error("Failed to initialize coordinate transformers: %s", e)
    raise


@lru_cache(maxsize=1)
def load_alkmaar_polygon_rd():
    """Load Alkmaar municipality polygon and transform it to RD.

    Cached so repeated per-station calls don't re-parse and re-project the file.
    """
    with ALKMAAR_POLYGON_FILE.open("r", encoding="utf-8") as f:
        feature = json.load(f)

    polygon_wgs = shape(feature["geometry"])

    if not polygon_wgs.is_valid:
        polygon_wgs = make_valid(polygon_wgs)

    return transform(to_rd, polygon_wgs)


def get_terrain_analysis(lat: float, lon: float, buffer_300m: int = 300, buffer_500m: int = 500, limit: int = 1000):
    """
    Fetch and analyze terrain data around a given lat/lon point.

    Args:
        lat: Latitude of the center point
        lon: Longitude of the center point
        buffer_300m: 300m area buffer radius in meters
        buffer_500m: 500m area buffer radius in meters
        limit: Maximum number of features to fetch per API request

    Returns:
        Dictionary with terrain percentages and counts
    """

    config = {
        "BUFFER_300M": buffer_300m,
        "BUFFER_500M": buffer_500m,
        "LIMIT": limit,
        "lat": lat,
        "lon": lon,
        "CATEGORY_MAP": {
            "lage vegetatie": {
                "heide",
                "duin",
                "grasland overig",
                "rietland",
                "kwelder",
                "bouwland",
                "grasland agrarisch",
                "groenvoorziening: planten",
                "groenvoorziening: struikrozen",
                "groenvoorziening: heesters",
                "groenvoorziening: bodembedekkers",
                "groenvoorziening: gras- en kruidachtigen",
                "transitie",
            },
            "middelhoge vegetatie": {
                "struiken",
                "fruitteelt",
                "fruitteelt: laagstam boomgaarden",
                "fruitteelt: wijngaarden",
                "fruitteelt: klein fruit",
                "boomteelt",
                "groenvoorziening",
            },
            "hoge vegetatie": {
                "gemengd bos",
                "naaldbos",
                "loofbos",
                "houtwal",
                "loofbos: griend en hakhout",
                "moeras",
                "fruitteelt: hoogstam boomgaarden",
                "groenvoorziening: bosplantsoen",
            },
        },
        "CATEGORY_TO_COLUMN": {
            "lage vegetatie": "oppervlak_lage_vegetatie_pct",
            "middelhoge vegetatie": "oppervlak_middelhoge_vegetatie_pct",
            "hoge vegetatie": "oppervlak_hoge_vegetatie_pct",
            "bebouwd gebied": "oppervlak_bebouwd_pct",
            "water": "oppervlak_water_pct",
            "weg": "oppervlak_wegen_pct",
            "pand": "oppervlak_panden_pct",
            "onverhard": "oppervlak_onverhard_pct",
        },
        "API_URLS": {
            "begroeid": "https://api.pdok.nl/lv/bgt/ogc/v1/collections/begroeidterreindeel/items",
            "onbegroeid": "https://api.pdok.nl/lv/bgt/ogc/v1/collections/onbegroeidterreindeel/items",
            "water": "https://api.pdok.nl/lv/bgt/ogc/v1/collections/waterdeel/items",
            "weg": "https://api.pdok.nl/lv/bgt/ogc/v1/collections/wegdeel/items",
            "pand": "https://api.pdok.nl/lv/bgt/ogc/v1/collections/pand/items",
        },
    }

    def fetch_features_tiled(url, minx, miny, maxx, maxy, limit, tiles):
        dx = (maxx - minx) / tiles
        dy = (maxy - miny) / tiles
        seen_ids = set()
        all_features = []
        any_tile_hit_limit = False

        for i in range(tiles):
            for j in range(tiles):
                params = {
                    "bbox": f"{minx + dx * i},{miny + dy * j},{minx + dx * (i + 1)},{miny + dy * (j + 1)}",
                    "f": "json",
                    "limit": limit,
                }
                resp = requests.get(url, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                features_in_tile = data.get("features", [])

                for feature in features_in_tile:
                    fid = feature.get("id")
                    if fid not in seen_ids:
                        seen_ids.add(fid)
                        all_features.append(feature)

                if len(features_in_tile) == limit:
                    any_tile_hit_limit = True
                    return all_features, any_tile_hit_limit

        return all_features, any_tile_hit_limit

    def get_category(type_value, category_map):
        for category, types in category_map.items():
            if type_value in types:
                return category
        return None

    def clip_feature_to_buffer(geom, buffer_rd):
        try:
            geom_rd = transform(to_rd, geom)
            clipped_geom = geom_rd.intersection(buffer_rd)

            if not clipped_geom.is_valid:
                clipped_geom = make_valid(clipped_geom)

            if clipped_geom.is_empty:
                return None

            return transform(to_wgs, clipped_geom)

        except ValueError as e:
            logger.debug("Geometry value error in clip_feature_to_buffer: %s", e)
            return None

        except TypeError as e:
            logger.debug("Geometry type error in clip_feature_to_buffer: %s", e)
            return None

    station_rd = to_rd(lon, lat)
    buffer_rd_500m = Point(station_rd).buffer(buffer_500m)
    buffer_rd_300m = Point(station_rd).buffer(buffer_300m)
    buffer_wgs_500m = transform(to_wgs, buffer_rd_500m)
    buffer_area_500m = buffer_rd_500m.area
    buffer_area_300m = buffer_rd_300m.area

    alkmaar_polygon_rd = load_alkmaar_polygon_rd()

    in_alkmaar_pct_300m = (buffer_rd_300m.intersection(alkmaar_polygon_rd).area / buffer_area_300m) * 100

    in_alkmaar_pct_500m = (buffer_rd_500m.intersection(alkmaar_polygon_rd).area / buffer_area_500m) * 100

    bminx, bminy, bmaxx, bmaxy = buffer_wgs_500m.bounds

    features_dict = {}
    tiles_dict = {key: 1 for key in config["API_URLS"]}

    fetch_failures = {}

    for key, url in config["API_URLS"].items():
        current_tiles = tiles_dict[key]
        hit_limit = True
        features_dict[key] = []

        while hit_limit:
            hit_limit = False
            try:
                features, tile_hit_limit = fetch_features_tiled(url, bminx, bminy, bmaxx, bmaxy, limit, current_tiles)
                features_dict[key] = features

                if tile_hit_limit:
                    hit_limit = True
                    current_tiles += 1
                    tiles_dict[key] = current_tiles

            except RequestException as e:
                logger.warning("HTTP error while fetching %s features: %s", key, e)
                fetch_failures[key] = f"http_error: {e}"
                break

            except ValueError as e:
                logger.warning("JSON/parse error while fetching %s features: %s", key, e)
                fetch_failures[key] = f"parse_error: {e}"
                break

    api_key_to_category = {
        "begroeid": list(config["CATEGORY_MAP"]),
        "onbegroeid": "bebouwd gebied",
        "water": "water",
        "weg": "weg",
        "pand": "pand",
    }

    seen_geometries = set()

    category_geometries_500m = {category: [] for category in config["CATEGORY_TO_COLUMN"]}
    category_geometries_300m = {category: [] for category in config["CATEGORY_TO_COLUMN"]}

    feature_warning_count = {}
    feature_warning_limit = 5

    def log_limited_warning(key: str, message: str):
        feature_warning_count[key] = feature_warning_count.get(key, 0) + 1
        if feature_warning_count[key] <= feature_warning_limit:
            logger.warning(message)
        elif feature_warning_count[key] == feature_warning_limit + 1:
            logger.warning("Further warnings of type '%s' will be suppressed", key)

    # Process vegetated areas
    for feature in features_dict.get("begroeid", []):
        try:
            geom = shape(feature["geometry"])
            geom_wkt = geom.wkt

            if geom_wkt not in seen_geometries:
                seen_geometries.add(geom_wkt)
                clipped_geom_500m = clip_feature_to_buffer(geom, buffer_rd_500m)
                clipped_geom_300m = clip_feature_to_buffer(geom, buffer_rd_300m)

                if clipped_geom_500m or clipped_geom_300m:
                    props = feature["properties"]
                    fysiek_voorkomen = props.get("fysiek_voorkomen", "")
                    plus_fysiek_voorkomen = props.get("plus_fysiek_voorkomen", "")
                    type_value = (
                        f"{fysiek_voorkomen}: {plus_fysiek_voorkomen}" if plus_fysiek_voorkomen else fysiek_voorkomen
                    )

                    category = get_category(type_value, config["CATEGORY_MAP"])
                    if not category:
                        category = "lage vegetatie"

                    if clipped_geom_500m:
                        geom_rd_500m = transform(to_rd, clipped_geom_500m)
                        category_geometries_500m[category].append(geom_rd_500m)
                    if clipped_geom_300m:
                        geom_rd_300m = transform(to_rd, clipped_geom_300m)
                        category_geometries_300m[category].append(geom_rd_300m)

        except Exception as e:
            log_limited_warning("begroeid_process", f"Failed to process begroeid feature: {e}")

    # Process onbegroeid: split onverhard/zand vs rest (bebouwd gebied)
    onverhard_types = {"onverhard", "zand"}

    for feature in features_dict.get("onbegroeid", []):
        try:
            geom = shape(feature["geometry"])
            geom_wkt = geom.wkt

            if geom_wkt not in seen_geometries:
                seen_geometries.add(geom_wkt)
                clipped_geom_500m = clip_feature_to_buffer(geom, buffer_rd_500m)
                clipped_geom_300m = clip_feature_to_buffer(geom, buffer_rd_300m)

                if clipped_geom_500m or clipped_geom_300m:
                    fv = feature["properties"].get("fysiek_voorkomen", "")
                    category = "onverhard" if fv in onverhard_types else "bebouwd gebied"

                    if clipped_geom_500m:
                        category_geometries_500m[category].append(transform(to_rd, clipped_geom_500m))
                    if clipped_geom_300m:
                        category_geometries_300m[category].append(transform(to_rd, clipped_geom_300m))

        except Exception as e:
            log_limited_warning("onbegroeid_process", f"Failed to process onbegroeid feature: {e}")

    # Process other categories
    for api_key, features in features_dict.items():
        if api_key in ["begroeid", "onbegroeid"]:
            continue

        category = api_key_to_category.get(api_key, api_key)
        if isinstance(category, list) or category not in category_geometries_500m:
            continue

        for feature in features:
            try:
                geom = shape(feature["geometry"])
                geom_wkt = geom.wkt

                if geom_wkt not in seen_geometries:
                    seen_geometries.add(geom_wkt)
                    clipped_geom_500m = clip_feature_to_buffer(geom, buffer_rd_500m)
                    clipped_geom_300m = clip_feature_to_buffer(geom, buffer_rd_300m)

                    if clipped_geom_500m:
                        geom_rd_500m = transform(to_rd, clipped_geom_500m)
                        category_geometries_500m[category].append(geom_rd_500m)
                    if clipped_geom_300m:
                        geom_rd_300m = transform(to_rd, clipped_geom_300m)
                        category_geometries_300m[category].append(geom_rd_300m)

            except Exception as e:
                log_limited_warning(f"{api_key}_process", f"Failed to process {api_key} feature: {e}")

    # Merge geometries
    category_merged_geoms_500m = {}
    category_merged_geoms_300m = {}

    for category, geometries in category_geometries_500m.items():
        if geometries:
            merged_geom = unary_union(geometries)
            category_merged_geoms_500m[category] = None if merged_geom.is_empty else merged_geom
        else:
            category_merged_geoms_500m[category] = None

    for category, geometries in category_geometries_300m.items():
        if geometries:
            merged_geom = unary_union(geometries)
            category_merged_geoms_300m[category] = None if merged_geom.is_empty else merged_geom
        else:
            category_merged_geoms_300m[category] = None

    # Priority masking
    priority_order = ["pand", "weg", "bebouwd gebied", "hoge vegetatie", "middelhoge vegetatie"]
    masked_geoms_500m = {}
    masked_geoms_300m = {}
    covered_area_500m = None
    covered_area_300m = None

    for category in priority_order:
        if category in category_merged_geoms_500m and category_merged_geoms_500m[category]:
            if covered_area_500m is None:
                masked_geoms_500m[category] = category_merged_geoms_500m[category]
            else:
                masked_geoms_500m[category] = category_merged_geoms_500m[category].difference(covered_area_500m)

            if masked_geoms_500m[category].is_empty:
                masked_geoms_500m[category] = None
            else:
                covered_area_500m = (
                    masked_geoms_500m[category]
                    if covered_area_500m is None
                    else covered_area_500m.union(masked_geoms_500m[category])
                )

        if category in category_merged_geoms_300m and category_merged_geoms_300m[category]:
            if covered_area_300m is None:
                masked_geoms_300m[category] = category_merged_geoms_300m[category]
            else:
                masked_geoms_300m[category] = category_merged_geoms_300m[category].difference(covered_area_300m)

            if masked_geoms_300m[category].is_empty:
                masked_geoms_300m[category] = None
            else:
                covered_area_300m = (
                    masked_geoms_300m[category]
                    if covered_area_300m is None
                    else covered_area_300m.union(masked_geoms_300m[category])
                )

    for category in category_merged_geoms_500m:
        if category not in priority_order:
            if category_merged_geoms_500m[category]:
                if covered_area_500m is None:
                    masked_geoms_500m[category] = category_merged_geoms_500m[category]
                else:
                    masked_geoms_500m[category] = category_merged_geoms_500m[category].difference(covered_area_500m)
                    if masked_geoms_500m[category].is_empty:
                        masked_geoms_500m[category] = None
            else:
                masked_geoms_500m[category] = None

            if category_merged_geoms_300m[category]:
                if covered_area_300m is None:
                    masked_geoms_300m[category] = category_merged_geoms_300m[category]
                else:
                    masked_geoms_300m[category] = category_merged_geoms_300m[category].difference(covered_area_300m)
                    if masked_geoms_300m[category].is_empty:
                        masked_geoms_300m[category] = None
            else:
                masked_geoms_300m[category] = None

    category_areas_500m = {}
    category_areas_300m = {}

    for category, geom in masked_geoms_500m.items():
        if geom:
            category_areas_500m[category] = geom.area

    for category, geom in masked_geoms_300m.items():
        if geom:
            category_areas_300m[category] = geom.area

    percentages_500m = {cat: (area / buffer_area_500m) * 100 for cat, area in category_areas_500m.items()}
    percentages_300m = {cat: (area / buffer_area_300m) * 100 for cat, area in category_areas_300m.items()}

    bebouwd_area_percentage_500m = percentages_500m.get("pand", 0) + percentages_500m.get("bebouwd gebied", 0)
    bebouwd_area_percentage_300m = percentages_300m.get("pand", 0) + percentages_300m.get("bebouwd gebied", 0)

    onverhard_pct_500m = (
        percentages_500m.get("lage vegetatie", 0)
        + percentages_500m.get("water", 0)
        + percentages_500m.get("onverhard", 0)
    )
    onverhard_pct_300m = (
        percentages_300m.get("lage vegetatie", 0)
        + percentages_300m.get("water", 0)
        + percentages_300m.get("onverhard", 0)
    )

    percentages_500m = {cat: perc for cat, perc in percentages_500m.items() if cat not in ["pand", "bebouwd gebied"]}
    percentages_500m["bebouwd_area"] = bebouwd_area_percentage_500m

    percentages_300m = {cat: perc for cat, perc in percentages_300m.items() if cat not in ["pand", "bebouwd gebied"]}
    percentages_300m["bebouwd_area"] = bebouwd_area_percentage_300m

    return {
        "is_partial": bool(fetch_failures),
        "fetch_failures": fetch_failures,
        "buffer_300m": {
            "pct_in_alkmaar": round(in_alkmaar_pct_300m, 2),
            "oppervlak_lage_vegetatie_pct": round(percentages_300m.get("lage vegetatie", 0), 2),
            "oppervlak_middelhoge_vegetatie_pct": round(percentages_300m.get("middelhoge vegetatie", 0), 2),
            "oppervlak_hoge_vegetatie_pct": round(percentages_300m.get("hoge vegetatie", 0), 2),
            "oppervlak_water_pct": round(percentages_300m.get("water", 0), 2),
            "oppervlak_wegen_pct": round(percentages_300m.get("weg", 0), 2),
            "oppervlak_bebouwd_pct": round(bebouwd_area_percentage_300m, 2),
            "oppervlak_onverhard_pct": round(onverhard_pct_300m, 2),
            "oppervlak_onbebouwd_pct": round(percentages_300m.get("onverhard", 0), 2),
        },
        "buffer_500m": {
            "pct_in_alkmaar": round(in_alkmaar_pct_500m, 2),
            "oppervlak_lage_vegetatie_pct": round(percentages_500m.get("lage vegetatie", 0), 2),
            "oppervlak_middelhoge_vegetatie_pct": round(percentages_500m.get("middelhoge vegetatie", 0), 2),
            "oppervlak_hoge_vegetatie_pct": round(percentages_500m.get("hoge vegetatie", 0), 2),
            "oppervlak_water_pct": round(percentages_500m.get("water", 0), 2),
            "oppervlak_wegen_pct": round(percentages_500m.get("weg", 0), 2),
            "oppervlak_bebouwd_pct": round(bebouwd_area_percentage_500m, 2),
            "oppervlak_onverhard_pct": round(onverhard_pct_500m, 2),
            "oppervlak_onbebouwd_pct": round(percentages_500m.get("onverhard", 0), 2),
        },
    }
