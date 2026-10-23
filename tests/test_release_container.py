"""Keep the permitted output volume from relaxing other release isolation checks."""

import pytest

from scripts.check_release_container import validate_release_container


def inspection():
    return {
        "Config": {"User": "10001:10001"},
        "HostConfig": {
            "ReadonlyRootfs": True,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges:true"],
            "Tmpfs": {"/tmp": "rw,size=64m"},
        },
        "Mounts": [{"Type": "volume", "Name": "test_results", "Destination": "/var/lib/geo/results", "RW": True}],
    }


def test_expected_named_volume_is_allowed():
    validate_release_container(inspection())


@pytest.mark.parametrize(
    "mounts",
    [
        [],
        [{"Type": "bind", "Destination": "/var/lib/geo/results", "RW": True}],
        [{"Type": "volume", "Destination": "/var/lib/geo/results", "RW": False}],
        [{"Type": "volume", "Destination": "/other", "RW": True}],
        inspection()["Mounts"] * 2,
    ],
)
def test_only_the_dedicated_writable_named_volume_is_allowed(mounts):
    document = inspection()
    document["Mounts"] = mounts
    with pytest.raises(RuntimeError, match="named result volume"):
        validate_release_container(document)


@pytest.mark.parametrize(
    "property_name,value", [("ReadonlyRootfs", False), ("CapDrop", []), ("SecurityOpt", []), ("Tmpfs", {})]
)
def test_other_hardening_still_matters(property_name, value):
    document = inspection()
    document["HostConfig"][property_name] = value
    with pytest.raises(RuntimeError):
        validate_release_container(document)


def test_root_is_rejected():
    document = inspection()
    document["Config"]["User"] = "0:0"
    with pytest.raises(RuntimeError, match="non-root"):
        validate_release_container(document)
