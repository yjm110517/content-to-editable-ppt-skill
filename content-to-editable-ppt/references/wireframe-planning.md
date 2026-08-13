# Host Wireframe Planning

Load this reference only after a Content-to-PPT task reaches `p1_complete`. Image-to-Editable-PPT bypasses P2.

## Authority

Read only the Deck Request, Approved Outline, Projection Manifest, frozen Approved Slide Content, and structured Wireframe Layout Requirements. Do not return to raw materials and do not copy or rewrite approved text into the Wireframe Spec.

Use `content_refs` exactly once to place approved text. Use `semantic_source_refs` to show which approved content motivates an image, chart, or diagram zone; semantic references may repeat and do not create another text placement.

## Planning boundary

Plan one Spec per Slide ID. Deck Order belongs to the Manifest, not the page Spec. Use integer `normalized_10000` geometry and create real parent-child Region relationships. Use explicit Overlay or Overlap Groups for intentional intersections. A foreground Decoration requires an Overlay relationship.

Do not choose final color, font, shadow, texture, illustration style, image asset, or PowerPoint object decomposition. The SVG is a low-fidelity structural preview, not the Design Image.

## Validation and correction

Submit the complete Candidate once, then consume the deterministic Validation Report. A logical Planning Pass allows at most two bounded Contract Corrections and at most three actual Host Model Invocations including the initial planning call.

Every Correction Operation must reference a correctable Validation Issue. Do not change Layout Pattern, approved content, Authority Hash, a legal Semantic Source, or a legal Focal Region through Contract Correction. If validation reports `redesign_required`, stop instead of silently redesigning.

## Preview and feedback

Every page must render an SVG even when Preview mode is `internal_only`. Pause only when `pause_for_feedback` is true. User layout feedback records only the affected Slide IDs for a later Wireframe revision. User text changes terminate the old P2 State as `p1_revision_required`; route the original request back to P1, create and confirm a new Candidate revision, then initialize a new P2 Authority Bundle. Never resume the old P2 State with new content.
