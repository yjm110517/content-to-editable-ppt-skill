# P3.1 Icon Asset Resolution

Enter this stage only with an accepted P2 1.1 Manifest and a Deck Visual Direction bound to its canonical hash. Treat the Manifest as the business input; use the bound Markdown only for path, hash, Deck, Revision, and accepted-state preflight.

Resolve `role=icon` placeholders offline from pinned Tabler Outline 3.46.0. Unique exact canonical names and unique official aliases may be selected automatically. Every other selection must come from the deterministic Top-K inside the current Host pass. Do not call an independent Icon Reviewer or online service.

Create the Resolution Record once only after an accurate Tabler selection. Materialize it through Normalize, the existing SVG Sanitizer, Asset Manifest 1.4, and the Resolved Asset Consumption Contract. Never rewrite the Resolution Record with derived hashes. Before build, recompute the Sanitized SVG source hash.

The formal production decision is binary:

```text
accurate Tabler match
→ immutable Resolution Record
→ Sanitized SVG

no accurate Tabler match
→ Raster Handoff Pending
→ wait for an Approved Design Preview
```

Do not call the historical two-Tabler composition or programmatic-SVG paths. Raster Handoff Pending is not SVG resolution success and must not create a fake Asset Manifest success or Consumption Contract. Extraction occurs only after the current Design Preview is approved; it must bind the Preview hash, `visual_ref`, crop box, PNG hash, background-removal status, and extraction quality. Reject extraction that includes formal text, unrelated elements, the whole slide, insufficient resolution, severe background fusion, or occlusion.

P3.1 proves that the same Sanitized SVG source can be consumed by the Preview compositor and PowerPoint Runtime. It does not decide final color, size, position, slot, z-order, or create a formal Design Preview.
