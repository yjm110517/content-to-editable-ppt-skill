# Markdown Wireframe Execution

Use this workflow only after P1 reaches `p1_complete`. The formal P2 artifacts are `wireframes/deck-wireframe.md` and the thin `wireframes/wireframe-manifest.json`.

## Host Candidate

Produce one lightweight JSON Candidate 1.1 per Deck. For each slide provide `slide_id`, `order`, `layout_draft`, `content_labels`, `visual_placeholders`, and `layout_notes`.

- Use `{{p2:content-ref=S03-C01}}` exactly once for every approved Content Ref and in authority order.
- Set each label to a short continuous substring of the approved text.
- For every required visual, declare a Deck-unique `visual_ref`, `role`, optional diagram `subtype`, `semantic`, and current-page `semantic_source_refs`; place it exactly once with `{{p2:visual-ref=S03-V01}}`.
- Roles are `icon`, `image`, `chart`, `diagram`, or `illustration`. Diagram subtypes are `process`, `timeline`, `cycle`, `relationship`, or `architecture`. Only anonymous `whitespace` remains a zone.
- Keep library names, icon names, versions, paths, SVG, hashes, colors, strokes, and decoration out of P2. Those are resolved in P3.
- Keep free page copy out of `layout_draft`. Put hierarchy, relationships, reserved visual areas, and reading order in `layout_notes`.
- Do not write HTML metadata. The deterministic Binder inserts it.

Run `manage_wireframe.py submit-candidate`. Correct only reported contract issues, bind every Patch operation to `validation_issue_id`, and stop after two corrections. Do not automatically redesign.

## Bind and show

Run `bind` only after Candidate validation passes. It reads the actual P1 Authority, injects every complete approved title and Content Block, creates the text layout and notes, audits the result, and writes an immutable revision.

Show the entire generated Markdown to the user by default, then record `user_visible`. Record `skipped` only when the user explicitly asks not to view the wireframe.

- `continue` or `accepted`: publish the accepted revision and complete P2.
- Layout changes: create a new P2 revision and preserve the old revision.
- Content changes: enter `p1_revision_required`; do not resume the old P2 State.

Run `verify` before proceeding. P2 must not generate SVG, PNG, PPTX, final styling, or visual assets. Sanitized SVG remains supported only as a later PowerPoint Runtime asset format.
