"""Build the runtime Vietnam administrative-unit dataset from a pinned source."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import urlopen

SOURCE_COMMIT = "8b78ba5118715e1fa81769286724db79346abf52"
SOURCE_URL = (
    "https://raw.githubusercontent.com/thanglequoc/"
    "vietnamese-provinces-database/"
    f"{SOURCE_COMMIT}/json/full_json_generated_data_vn_units.json"
)
OUTPUT = Path(__file__).resolve().parents[1] / "app" / "data" / "vn_admin_units_2025.json"


def main() -> None:
    with urlopen(SOURCE_URL, timeout=30) as response:  # noqa: S310 - pinned HTTPS source
        source = json.load(response)

    provinces = []
    commune_codes: set[str] = set()
    for province in source:
        communes = []
        for commune in province["Wards"]:
            code = commune["Code"]
            if len(code) != 5 or code in commune_codes:
                raise ValueError(f"Invalid or duplicate commune code: {code}")
            if commune["ProvinceCode"] != province["Code"]:
                raise ValueError(f"Invalid parent for commune: {code}")
            commune_codes.add(code)
            full_name = f"{commune['AdministrativeUnitShortName']} {commune['Name']}"
            communes.append({"code": code, "name": full_name})
        provinces.append(
            {
                "code": province["Code"],
                "name": f"{province['AdministrativeUnitShortName']} {province['Name']}",
                "communes": communes,
            }
        )

    province_codes = {province["code"] for province in provinces}
    if len(provinces) != 34 or len(province_codes) != 34:
        raise ValueError("Expected 34 unique province-level units")
    if any(len(code) != 2 for code in province_codes):
        raise ValueError("Province codes must contain two digits")
    if len(commune_codes) != 3321:
        raise ValueError("Expected 3,321 unique commune-level units")

    output = {
        "metadata": {
            "version": "2025-07-01",
            "legal_basis": "Decision 19/2025/QD-TTg",
            "source": SOURCE_URL,
            "source_license": "MIT",
            "province_count": 34,
            "commune_count": 3321,
        },
        "provinces": provinces,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT} ({len(provinces)} provinces, {len(commune_codes)} communes)")


if __name__ == "__main__":
    main()
