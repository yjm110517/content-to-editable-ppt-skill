from __future__ import annotations

from decimal import Decimal
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

SLIDE_RATIO_RELATIVE_TOLERANCE = Decimal("0.001")


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


def validate_slide_ratio_compatible(output_ratio: str, width_in: float, height_in: float) -> SlideSize:
    """Accept harmless Planner precision drift while enforcing the requested aspect ratio."""

    expected = resolve_slide_size(output_ratio)
    actual_width = Decimal(str(width_in))
    actual_height = Decimal(str(height_in))
    if actual_width <= 0 or actual_height <= 0:
        raise ContractError([
            error("$.slide", "Planner slide dimensions must be positive", "slide_ratio_mismatch")
        ])
    actual_ratio = actual_width / actual_height
    expected_ratio = Decimal(str(expected["width_in"])) / Decimal(str(expected["height_in"]))
    relative_error = abs(actual_ratio - expected_ratio) / expected_ratio
    if relative_error > SLIDE_RATIO_RELATIVE_TOLERANCE:
        raise ContractError([
            error(
                "$.slide",
                (
                    f"Planner slide ratio differs from Runtime policy for {output_ratio} "
                    f"by {relative_error:.6f}"
                ),
                "slide_ratio_mismatch",
            )
        ])
    return expected
