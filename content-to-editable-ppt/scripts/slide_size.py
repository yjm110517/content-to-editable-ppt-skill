from __future__ import annotations

from typing import TypedDict

from schema_utils import ContractError, error


class SlideSize(TypedDict):
    width_in: float
    height_in: float
    width_px: int
    height_px: int


DIMENSIONS: dict[str, SlideSize] = {
    "16:9": {"width_in": 13.333, "height_in": 7.5, "width_px": 1600, "height_px": 900},
    "4:3": {"width_in": 10.0, "height_in": 7.5, "width_px": 1200, "height_px": 900},
}


def resolve_slide_size(output_ratio: str) -> SlideSize:
    """Resolve the Runtime's canonical slide size for a supported ratio."""

    try:
        return dict(DIMENSIONS[output_ratio])  # type: ignore[return-value]
    except KeyError as exc:
        raise ContractError([
            error(
                "$.output_ratio",
                f"unsupported output ratio: {output_ratio}",
                "unsupported_output_ratio",
            )
        ]) from exc
