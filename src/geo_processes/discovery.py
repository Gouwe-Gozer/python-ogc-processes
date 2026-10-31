"""Focused discovery corrections shared by synchronous and async managers."""

import json
import re
from copy import copy
from urllib.parse import urlencode

from flask import render_template_string
from pygeoapi.api import conformance as upstream_conformance
from pygeoapi.api import evaluate_limit
from pygeoapi.api.processes import describe_processes
from pygeoapi.util import render_j2_template

FORMATS = {"json": "application/json", "html": "text/html", "jsonld": "application/ld+json"}
CONFORMANCE_REL = "http://www.opengis.net/def/rel/ogc/1.0/conformance"
JOB_LIST_CONFORMANCE_URI = "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/job-list"
CALLBACK_CONFORMANCE_URI = "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/callback"
FEATURES_CRUD = "http://www.opengis.net/spec/ogcapi-features-4/1.0/conf/create-replace-delete"
CQL_CLASSES = {
    "http://www.opengis.net/spec/cql2/1.0/conf/basic-cql2",
    "http://www.opengis.net/spec/cql2/1.0/conf/cql2-text",
}


def readonly_geojson_collections(config):
    """Scope corrections to the known, single-provider read-only GeoJSON case."""
    return {
        identifier
        for identifier, resource in config["resources"].items()
        if len(providers := resource.get("providers", [])) == 1
        and providers[0].get("type") == "feature"
        and providers[0].get("name") == "GeoJSON"
        and not providers[0].get("editable", False)
    }


def conformance(api, request):
    """Correct inherited claims while retaining native discovery and templates.

    pygeoapi 0.24.0 appends static Callback/Features/CQL2 classes without
    checking subscriber support, editability or filterq evaluation.
    """
    providers = [
        provider for resource in api.config["resources"].values() for provider in resource.get("providers", [])
    ]
    features = [provider for provider in providers if provider.get("type") == "feature"]
    excluded = set()
    if not api.manager.supports_subscribing:
        excluded.add(CALLBACK_CONFORMANCE_URI)
    if features and not any(provider.get("editable", False) for provider in features):
        excluded.add(FEATURES_CRUD)
    if providers and all(
        provider.get("type") == "feature" and provider.get("name") == "GeoJSON" and not provider.get("editable", False)
        for provider in providers
    ):
        excluded.update(CQL_CLASSES)
    job_list = getattr(api.manager, "supports_job_list", False)
    if not job_list:
        excluded.add(JOB_LIST_CONFORMANCE_URI)
    value_request = copy(request)
    value_request._format = "json"
    _headers, status, body = upstream_conformance(api, value_request)
    document = json.loads(body)
    document["conformsTo"] = [uri for uri in document["conformsTo"] if uri not in excluded]
    if job_list and JOB_LIST_CONFORMANCE_URI not in document["conformsTo"]:
        document["conformsTo"].append(JOB_LIST_CONFORMANCE_URI)
    headers = request.get_response_headers(**api.api_headers)
    if request.format == "html":
        body = render_j2_template(
            api.tpl_config, api.config["server"]["templates"], "conformance.html", document, request.locale
        )
    else:
        body = json.dumps(document, indent=2 if api.pretty_print else None)
    return headers, status, body


def _navigation(links):
    return render_template_string(
        '<nav aria-label="API links">{% for link in links %}'
        '<a rel="{{ link.rel }}" type="{{ link.type }}" href="{{ link.href }}">{{ link.rel }}</a> '
        "{% endfor %}</nav>",
        links=links,
    )


def list_processes(api, request):
    """Preserve filters in self/alternate links and make limited lists traversable."""
    headers = request.get_response_headers(**api.api_headers)
    if request.format not in {None, *FORMATS}:
        return api.get_format_exception(request)
    try:
        for name in ("limit", "offset"):
            if name in request.params and re.fullmatch(r"[0-9]+", request.params[name]) is None:
                raise ValueError(f"{name} must be an integer")
        limit = evaluate_limit(request.params.get("limit"), api.config["server"].get("limits", {}), {})
        offset = int(request.params.get("offset", "0"))
    except ValueError as error:
        return api.get_exception(400, headers, request.format, "InvalidParameterValue", str(error))

    identifiers = list(api.manager.processes)
    value_request = copy(request)
    # Only this local copy changes. Let pinned upstream create translated
    # descriptions/links, rather than duplicating processor metadata machinery.
    value_request._format = "json"
    summaries = []
    for identifier in identifiers[offset : offset + limit]:
        _, status, body = describe_processes(api, value_request, identifier)
        if status != 200:
            return api.get_exception(500, headers, request.format, "NoApplicableCode", "process discovery failed")
        summary = json.loads(body)
        for key in ("inputs", "outputs", "example"):
            summary.pop(key, None)
        summaries.append(summary)
    base = f"{api.base_url}/processes"
    query = dict(request.params)

    def link(format_, relation, page_offset=offset):
        params = {**query, "limit": limit, "offset": page_offset, "f": format_}
        return {"href": f"{base}?{urlencode(params)}", "rel": relation, "type": FORMATS[format_]}

    format_ = request.format or "json"
    links = [link(name, "self" if name == format_ else "alternate") for name in FORMATS]
    if offset + limit < len(identifiers):
        links.append(link(format_, "next", offset + limit))
    if offset:
        links.append(link(format_, "prev", max(0, offset - limit)))
    document = {"processes": summaries, "links": links}
    if format_ == "html":
        body = render_j2_template(
            api.tpl_config, api.config["server"]["templates"], "processes/index.html", document, request.locale
        )
        body = body.replace("</body>", _navigation(links) + "</body>")
    else:
        body = json.dumps(document, indent=2 if api.pretty_print else None)
    headers["Link"] = ", ".join(f'<{item["href"]}>; rel="{item["rel"]}"; type="{item["type"]}"' for item in links)
    return headers, 200, body


def landing_links(response, api):
    """Core req. 2 uses an absolute OGC conformance relation, unlike upstream."""
    links = [
        {
            "rel": "service-desc",
            "href": f"{api.base_url}/openapi",
            "type": "application/vnd.oai.openapi+json;version=3.0",
        },
        {"rel": CONFORMANCE_REL, "href": f"{api.base_url}/conformance", "type": "application/json"},
        {
            "rel": "http://www.opengis.net/def/rel/ogc/1.0/processes",
            "href": f"{api.base_url}/processes",
            "type": "application/json",
        },
    ]
    # JSON-LD is also JSON, but upstream returns a DataCatalog with no links
    # array. Preserve that representation and supply the HTTP links below.
    if response.mimetype == "application/json":
        document = response.get_json()
        body_links = document.get("links") if isinstance(document, dict) else None
        if isinstance(body_links, list):
            if not any(isinstance(item, dict) and item.get("rel") == CONFORMANCE_REL for item in body_links):
                body_links.append(links[1])
            response.set_data(json.dumps(document, indent=2 if api.pretty_print else None))
    elif response.mimetype == "text/html":
        response.set_data(response.get_data(as_text=True).replace("</body>", _navigation(links) + "</body>"))
    for item in links:
        response.headers.add("Link", f'<{item["href"]}>; rel="{item["rel"]}"; type="{item["type"]}"')
    return response
