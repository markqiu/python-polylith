import re
from functools import reduce
from pathlib import Path
from typing import List, Union

import tomlkit
from polylith import repo


def transform_to_package(namespace: str, include: str) -> dict:
    path, _separator, brick = str.partition(include, f"/{namespace}/")

    return {"include": f"{namespace}/{brick}", "from": path}


def get_polylith_section(data) -> dict:
    return data.get("tool", {}).get("polylith", {})


def get_custom_top_namespace_from_polylith_section(data) -> Union[str, None]:
    poly_data = get_polylith_section(data)

    return poly_data.get("build", {}).get("top-namespace")


def get_project_packages_from_polylith_section(data) -> dict:
    poly_data = get_polylith_section(data)

    bricks = poly_data.get("bricks")

    return bricks if isinstance(bricks, dict) else {}


def get_hatch_project_packages(data) -> dict:
    polylith_section = get_project_packages_from_polylith_section(data)

    if polylith_section:
        return polylith_section

    hatch_data = data["tool"]["hatch"]
    build_data = hatch_data.get("build", {}) if isinstance(hatch_data, dict) else {}

    return build_data.get("force-include", {})


def get_project_package_includes(namespace: str, data) -> List[dict]:
    if repo.is_poetry(data):
        return data["tool"]["poetry"].get("packages", [])

    includes = (
        get_hatch_project_packages(data)
        if repo.is_hatch(data)
        else get_project_packages_from_polylith_section(data)
    )

    return [transform_to_package(namespace, key) for key in includes.keys()]


def get_project_name(data) -> str:
    if repo.is_pep_621_ready(data):
        return data["project"]["name"]

    return data["tool"]["poetry"]["name"]


def parse_pep_621_dependency(dep: str) -> dict:
    parts = re.split(r"[\^~=!<>]", dep)

    name, *_ = parts if parts else [""]
    version = str.replace(dep, name, "")

    return {name: version} if name else {}


def parse_poetry_dependency(acc: dict, kv: tuple) -> dict:
    k, v = kv

    if isinstance(v, dict):
        extras = sorted(v.get("extras", []))
        version = v.get("version", "")

        name = k + str.replace(f"{extras}", "'", "") if extras else k
        parsed = {name: version}
    else:
        parsed = {k: v}

    return {**acc, **parsed}


def parse_project_dependencies(data) -> dict:
    if repo.is_poetry(data):
        deps = data["tool"]["poetry"].get("dependencies", {})
        res: dict = reduce(parse_poetry_dependency, deps.items(), {})

        return res

    deps = data["project"].get("dependencies", [])

    return {k: v for dep in deps for k, v in parse_pep_621_dependency(dep).items()}


def get_project_dependencies(data) -> dict:
    items = parse_project_dependencies(data)

    return {"items": items, "source": repo.default_toml}


def read_toml_document(path: Path) -> tomlkit.TOMLDocument:
    with path.open(encoding="utf-8", errors="ignore") as f:
        return tomlkit.loads(f.read())
