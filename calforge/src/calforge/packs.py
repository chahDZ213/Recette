"""CalForge pack format — the open interchange format for map definitions.

A pack is a JSON document (``*.calpack.json``) validated by the Pydantic
models below. Design goals: human-readable, diff-friendly, hand-editable,
and stable across versions (the ``format`` field is versioned).

Example
-------
::

    {
      "format": "calforge-pack/1",
      "name": "Golf 7 GTI MG1CS111 — pack personnel",
      "description": "Cartographies identifiées sur la base 8V0906259H",
      "matchers": [
        {"kind": "sha256", "sha256": "9f2a…"},
        {"kind": "signature", "offset": "0x300", "hex": "8V0906259H"},
        {"kind": "size", "size": 4194304}
      ],
      "maps": [
        {
          "name": "Injection — charge/régime",
          "category": "injection",
          "offset": "0x8020",
          "rows": 16, "cols": 16,
          "element_size": 2, "endianness": "le",
          "factor": 0.0234375, "value_offset": 0.0, "unit": "mg/cp"
        }
      ]
    }

Offsets accept plain integers or ``"0x…"`` hex strings. ``hex`` in a
signature matcher is either a hex byte string (``"DEADBEEF"``) or, for
convenience, ASCII prefixed with ``ascii:`` (``"ascii:8V0906259H"``).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

PACK_FORMAT = "calforge-pack/1"


def _parse_offset(value: object) -> object:
    if isinstance(value, str):
        return int(value.strip(), 16 if value.strip().lower().startswith("0x") else 10)
    return value


class Sha256Matcher(BaseModel):
    kind: Literal["sha256"]
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")


class SignatureMatcher(BaseModel):
    kind: Literal["signature"]
    offset: int = Field(ge=0)
    hex: str = Field(min_length=1)

    _parse_offset = field_validator("offset", mode="before")(_parse_offset)

    @field_validator("hex")
    @classmethod
    def _normalise_hex(cls, value: str) -> str:
        if value.startswith("ascii:"):
            return value[len("ascii:") :].encode("ascii").hex().upper()
        cleaned = value.replace(" ", "")
        bytes.fromhex(cleaned)  # raises ValueError on invalid hex
        return cleaned.upper()

    @property
    def pattern(self) -> bytes:
        return bytes.fromhex(self.hex)


class SizeMatcher(BaseModel):
    kind: Literal["size"]
    size: int = Field(gt=0)


PackMatcher = Annotated[
    Sha256Matcher | SignatureMatcher | SizeMatcher, Field(discriminator="kind")
]


class PackMap(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(default="other", max_length=50)
    offset: int = Field(ge=0)
    rows: int = Field(ge=1, le=1024)
    cols: int = Field(ge=1, le=1024)
    element_size: Literal[1, 2] = 2
    endianness: Literal["le", "be", ""] = "le"
    factor: float = 1.0
    value_offset: float = 0.0
    unit: str = Field(default="", max_length=30)
    description: str = ""

    _parse_offset = field_validator("offset", mode="before")(_parse_offset)


class Pack(BaseModel):
    format: Literal["calforge-pack/1"]
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    matchers: list[PackMatcher] = Field(default_factory=list)
    maps: list[PackMap] = Field(min_length=1)
