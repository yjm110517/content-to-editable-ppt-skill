# P4 Constrained Reconstruction

Enter P4 only with `p3_3_complete`, an approved Design Preview Manifest, passing Reconstruction Compatibility evidence, complete Reconstruction Seeds, frozen P1 text, approved SVG/raster assets, and any required PowerPoint Chart Specs.

Run the production workflow through `manage_reconstruction.py`:

1. `init` closes the P3.3 Preview, Element Map, Compatibility, Deck, Slide and Hash authority chain.
2. `build-asset-manifest` records the actual approved independent asset bytes without rewriting P3.3 evidence.
3. `build-seed-view` deterministically merges Element Map geometry with frozen text, typography, chart and asset authority. If any Critical/Major seed is incomplete, return to P3.3. Do not ask a Planner to infer it from preview pixels.
4. `compile-spec` projects the complete Seed View without an initial Planner call. Declare order bindings only for page numbers, section ordinals, progress or navigation that truly depend on deck order.
5. Select a one-page Smoke Set when it covers every reconstruction class; add at most one second page when it materially increases coverage. Require a production fixture for any remaining class.
6. Build and render pages with the shared P3.3/P4 PowerPoint builders. Formal text remains native text, cards/connectors remain native shapes, charts remain native charts, and approved SVG/raster assets remain independent objects. Never insert the Raw Generated Layer or a full-slide raster substitute.
7. Use deterministic visual metrics only to find anomalies. They do not assign Critical/Major severity by themselves. Invoke a Reviewer only for an exception checkpoint.
8. Apply at most two issue-bound Targeted Patches. Never patch content, identity, Reconstruction Class, P4 Strategy, asset identity, chart data, Seed authority or Approved Preview. A third patch or any required authority change returns to P3.3 or fails explicitly.
9. Assemble `reconstruction-candidate.pptx` with the same shared builders, render every assembled slide through Microsoft PowerPoint, and require each candidate-deck render to be byte-identical to its last-passed page render.
10. Run `verify`. A passing P4 candidate remains `delivery_forbidden=true`; P5 performs final Deck consistency review, packaging and delivery.

Technical retries reuse the same Spec and never invoke a Planner. The maximum is the initial attempt plus two technical retries per stage.
