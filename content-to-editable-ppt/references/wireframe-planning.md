# Markdown Wireframe Migration Boundary

ADR-035 supersedes the historical SVG-based P2 workflow. The formal Wireframe is now defined as a Host-generated Markdown document that shows the real approved content and a per-slide layout draft.

The Markdown Binder, thin Manifest, Validator, revision workflow, and new P2 Gate have not yet been implemented. Until that implementation is complete:

- stop after `content_to_ppt + p1_complete`;
- report `P2 Markdown realignment pending`;
- do not invoke `manage_wireframe.py`, `validate_wireframe.py`, `render_wireframe.py`, or the historical SVG P2 route;
- do not enter P3;
- preserve all P1 Approved Slide Content without rewriting it.

The future formal artifacts are:

```text
wireframes/deck-wireframe.md
wireframes/wireframe-manifest.json
```

`deck-wireframe.md` will contain each slide's complete approved content, a text-based layout draft, and layout notes. The thin Manifest will bind Deck identity, P1 Authority hashes, Slide IDs, order, Content Refs, revision, Markdown hash, and status. It will not contain coordinates, regions, SVG data, or final visual style.

This deprecation applies only to SVG as the P2 Wireframe representation. Sanitized SVG remains a supported visual asset format in the single-slide PowerPoint Runtime.
