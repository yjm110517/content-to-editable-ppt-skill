# P3.2 Visual System and Prompt Contract

Enter with closed P1/P2 Authority and a P3.1 Icon Asset Index that covers every Icon Placeholder as either `resolved_svg` or `raster_handoff_pending`.

Keep visual rules in two layers. Hard Constraints protect fonts, palette, ratio, safe areas, Text Footprints, Authority, compositor ownership, and prohibitions. Soft Design Guidance recommends grids, template families, cards, imagery, rhythm, asymmetry, overlap, and visual focus; never convert it into fixed page BBoxes.

Use `manage_visual_system.py` to validate and freeze one Host candidate, compile Text Footprints from actual font files, compile page prompts, and verify the final hashes. Permit at most one issue-bound Contract Correction. Never redesign automatically.

Treat P1 text as quoted semantic data. The generated layer must not draw formal text, resolved SVG, or formal chart labels. Raster Handoff candidates must be isolated, text-free, unoccluded, separated from the background, and surrounded by safe padding.

The output is a Contract/Prompt Gate only. `Generated Visual Layer` is not a Final or Approved Design Preview. P3.3 must compose formal text, resolved SVG, and deterministic chart previews before asking the user to approve anything.
