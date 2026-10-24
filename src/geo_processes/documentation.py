"""Use pygeoapi's template override for the compatible ReDoc presentation."""

from pathlib import Path

from pygeoapi.util import TEMPLATESDIR


def configure_documentation_templates(api):
    """Replace only the upstream default; keep an operator's custom path."""
    templates = api.config["server"]["templates"]
    if Path(templates.get("path", TEMPLATESDIR)) == TEMPLATESDIR:
        path = str(Path(__file__).with_name("templates"))
        templates["path"] = path
        api.tpl_config["server"]["templates"]["path"] = path
