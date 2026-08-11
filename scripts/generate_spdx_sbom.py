#!/usr/bin/env python3
"""Generate a deterministic-shape SPDX 2.3 SBOM for a public Beta Marketplace."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote


BETA_VERSION = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-beta\.([1-9]\d*)$"
)
REVISION = re.compile(r"^[0-9a-fA-F]{40}$")
CREATED = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
GO_REQUIRE = re.compile(r"^([A-Za-z0-9._~/-]+)\s+(v[^\s]+)$")
PYTHON_REQUIRE = re.compile(r"^([A-Za-z0-9._-]+)==([^\s]+)$")
ROOT_PACKAGE_ID = "SPDXRef-Package-VivagoAgent-CLI"


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marketplace", type=Path, required=True)
    parser.add_argument("--go-mod", type=Path, required=True)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--created", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def _identifier(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
    return f"SPDXRef-{prefix}-{digest}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _go_dependencies(go_mod: Path) -> tuple[str, list[tuple[str, str]]]:
    module = ""
    dependencies: list[tuple[str, str]] = []
    for raw_line in go_mod.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line or line in {"require (", ")"}:
            continue
        if line.startswith("module "):
            module = line.removeprefix("module ").strip()
            continue
        if line.startswith("require "):
            line = line.removeprefix("require ").strip()
        match = GO_REQUIRE.fullmatch(line)
        if match is not None:
            dependencies.append((match.group(1), match.group(2)))
    if not module:
        raise ValueError("go.mod is missing the module path")
    return module, sorted(set(dependencies))


def _python_dependencies(requirements: Path) -> list[tuple[str, str]]:
    dependencies: list[tuple[str, str]] = []
    for raw_line in requirements.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = PYTHON_REQUIRE.fullmatch(line)
        if match is None:
            raise ValueError(f"Python build dependency is not exactly pinned: {line}")
        dependencies.append((match.group(1), match.group(2)))
    return sorted(set(dependencies))


def _package(
    *,
    spdx_id: str,
    name: str,
    version: str,
    purl: str,
    declared_license: str = "NOASSERTION",
) -> dict[str, object]:
    return {
        "SPDXID": spdx_id,
        "name": name,
        "versionInfo": version,
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": False,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": declared_license,
        "copyrightText": "NOASSERTION",
        "externalRefs": [
            {
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": purl,
            }
        ],
    }


def generate(args: argparse.Namespace) -> dict[str, object]:
    if not BETA_VERSION.fullmatch(args.version):
        raise ValueError("beta version must match X.Y.Z-beta.N with N greater than zero")
    if not REVISION.fullmatch(args.source_revision):
        raise ValueError("source revision must be a full 40-character Git SHA")
    if not CREATED.fullmatch(args.created):
        raise ValueError("created must be an RFC 3339 UTC timestamp without fractional seconds")
    marketplace = args.marketplace.resolve()
    if not marketplace.is_dir():
        raise ValueError("Marketplace directory does not exist")
    module, go_dependencies = _go_dependencies(args.go_mod)
    python_dependencies = _python_dependencies(args.requirements)

    root_purl = f"pkg:golang/{quote(module, safe='/')}@{quote(args.version, safe='')}"
    packages = [
        _package(
            spdx_id=ROOT_PACKAGE_ID,
            name=module,
            version=args.version,
            purl=root_purl,
            declared_license="Apache-2.0",
        )
    ]
    relationships: list[dict[str, str]] = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": ROOT_PACKAGE_ID,
        }
    ]
    for name, version in go_dependencies:
        spdx_id = _identifier("GoPackage", f"{name}@{version}")
        packages.append(
            _package(
                spdx_id=spdx_id,
                name=name,
                version=version,
                purl=f"pkg:golang/{quote(name, safe='/')}@{quote(version, safe='')}",
            )
        )
        relationships.append(
            {
                "spdxElementId": ROOT_PACKAGE_ID,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": spdx_id,
            }
        )
    for name, version in python_dependencies:
        spdx_id = _identifier("PythonPackage", f"{name}@{version}")
        packages.append(
            _package(
                spdx_id=spdx_id,
                name=name,
                version=version,
                purl=f"pkg:pypi/{quote(name.lower(), safe='')}@{quote(version, safe='')}",
            )
        )
        relationships.append(
            {
                "spdxElementId": ROOT_PACKAGE_ID,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": spdx_id,
            }
        )

    output = args.output.resolve()
    files: list[dict[str, object]] = []
    for path in sorted(marketplace.rglob("*")):
        if not path.is_file() or path.resolve() == output:
            continue
        relative = path.relative_to(marketplace).as_posix()
        spdx_id = _identifier("File", relative)
        files.append(
            {
                "SPDXID": spdx_id,
                "fileName": f"./{relative}",
                "checksums": [{"algorithm": "SHA256", "checksumValue": _sha256(path)}],
                "licenseConcluded": "NOASSERTION",
                "copyrightText": "NOASSERTION",
            }
        )
        relationships.append(
            {
                "spdxElementId": ROOT_PACKAGE_ID,
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": spdx_id,
            }
        )

    document = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"vivago-agent-cli-{args.version}",
        "documentNamespace": (
            "https://github.com/HiDream-ai/vivago-agent-cli/"
            f"sbom/{args.version}/{args.source_revision.lower()}"
        ),
        "creationInfo": {
            "created": args.created,
            "creators": ["Tool: vivago-agent-cli-sbom-generator"],
        },
        "packages": packages,
        "files": files,
        "relationships": relationships,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document


def main(argv: list[str] | None = None) -> int:
    try:
        document = generate(_arguments(argv))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "name": document["name"],
                "packages": len(document["packages"]),
                "files": len(document["files"]),
            },
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
