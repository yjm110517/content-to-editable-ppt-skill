---
name: content-to-editable-ppt
description: Plan and freeze presentation content, generate Markdown wireframes, compile a Deck Visual System, approve design previews, reconstruct them as an editable multi-page PowerPoint, and complete P5 final integrity, live deck consistency review, and immutable delivery. Use for P1–P5 content-to-deck production, deterministic replay, repository development, and image-to-editable single-slide reconstruction.
---

# Content to Editable PPT

## Development status

The Skill has two independent entry paths. The Content-to-PPT path executes P1 through P5: confirmed content, Markdown Wireframes, resolved assets, approved design previews, editable reconstruction, deterministic final integrity, one trusted live Deck Consistency Review, and immutable delivery. The inherited Runtime also rebuilds reference images as editable single slides. D03 has passed the complete P5 Gate; each new Deck still requires its own trusted live review before formal delivery.

## Route content planning

1. Read [references/task-routing.md](references/task-routing.md) and record `content_to_ppt`, `image_to_editable_ppt`, or `needs_clarification`.
2. For Content-to-PPT, read [references/content-planning.md](references/content-planning.md), record material readiness, and stop on unreadable required material unless the user authorizes ignoring it.
3. In one initial Host planning pass, produce Material Understanding and a Candidate Outline whose titles and Content Blocks are the exact proposed slide text.
4. Render the deterministic Outline preview and stop for mandatory user confirmation.
5. Create a new Candidate revision only after an explicit user change request. Never regenerate automatically.
6. Read [references/outline-contract.md](references/outline-contract.md), bind confirmation to the Candidate canonical hash, and promote only a `confirmed` Candidate.
7. Project Approved Slide Content deterministically. Do not call the Host, Layout Planner, or Visual Reviewer after confirmation.

Image-to-Editable-PPT bypasses every P1 Outline stage and continues through the inherited single-slide workflow below.

## Generate P2 Markdown Wireframes

1. Require `content_to_ppt + p1_complete`, then read [references/wireframe-planning.md](references/wireframe-planning.md).
2. In one Host pass, produce Candidate 1.1. Use Content Ref placeholders, approved-text substring labels, and stable Visual Placeholder intents bound through `semantic_source_refs`; never name a library or concrete asset in P2.
3. Run `manage_wireframe.py submit-candidate`; use at most two issue-bound Contract Corrections and never redesign automatically.
4. Run `bind` to create the immutable revision Markdown and thin Manifest. Show the complete Markdown in chat by default.
5. Record `user_visible` preview and route feedback: layout changes create a new P2 revision; content changes return to P1; explicit skip records the user-message hash and completes without pausing.
6. Run `verify` before treating P2 as complete. Never generate SVG, PNG, PPTX, or final visual design in P2.

Image-to-Editable-PPT bypasses P2.

## Resolve P3.1 icon assets

After an accepted P2 1.1 Manifest, read [references/icon-asset-resolution.md](references/icon-asset-resolution.md). Resolve only `role=icon` placeholders from the pinned offline Tabler index. Materialize an accurate selection through the existing SVG sanitizer; when no accurate Tabler icon exists, record `Raster Handoff Pending` and stop that asset path until an Approved Design Preview exists. Never use the historical composition or programmatic-SVG fallback in the formal route. Do not parse placeholder business fields from Markdown, call an independent Icon Reviewer, use an online service, or generate the final Design Preview.

## Compile P3.2 visual design prompts

After P3.1 icon decisions close, read [references/visual-system-and-prompts.md](references/visual-system-and-prompts.md). Run one Host Deck Visual System pass, keep Hard Constraints separate from Soft Design Guidance, and allow at most one issue-bound Contract Correction. Compile actual-font Text Footprints, layer ownership, page prompts, cache keys, the representative Style Anchor Request, and the Contract/Prompt Gate deterministically. Do not generate an image or claim visual quality was evaluated.

## Produce P3.3 Approved Design Previews

Read [references/approved-design-preview.md](references/approved-design-preview.md). Generate one Style Anchor, classify every important visual with a Reconstruction Class and P4 Strategy, pass the Compatibility Gate, then build the user-visible Final Preview through Microsoft PowerPoint. Require explicit approval before generating the remaining pages. Reuse the Sanitized Style Reference, generate each remaining page once, and approve the final Contact Sheet. Never approve a Raw Generated Layer directly or infer missing Chart data.

## Reconstruct P4 editable candidate Deck

After P3.3 reaches `p3_3_complete`, read [references/constrained-reconstruction.md](references/constrained-reconstruction.md). Require complete Reconstruction Seeds, compile page Specs deterministically with zero Initial Planner calls, pass the bounded reconstruction-class Smoke Set, build and render every page with the shared P3.3/P4 PowerPoint builders, and compare each result with its Approved Design Preview. Assemble `reconstruction-candidate.pptx`, render every assembled slide again, and require Post-Assembly Slide Drift to remain zero. Never insert the Raw Generated Layer, replace a page with a full-slide raster, guess missing Seeds from pixels, or change content, assets, Reconstruction Class, or P4 Strategy. Targeted Patches are issue-bound and limited to two per page.

Treat the verified P4 candidate as `delivery_forbidden=true` until P5 completes. Never bypass the deterministic gate, trusted live Deck Consistency Review, Delivery Decision, or reverse-verified seven-file package.

## Core requirements

- Rebuild readable text as native PowerPoint text.
- Rebuild cards, borders, lines, arrows, labels, and simple diagrams as native shapes.
- Use sanitized SVG only for an accurate standard-library icon. Use isolated PNG or JPEG objects for unmatched icons, complex illustrations, photos, textures, 3D, gradients, highlights, shadows, depth, or irregular scene detail.
- Never replace a distinctive source icon with a Unicode glyph, letter, emoji, or generic polygon merely to maximize native editability.
- Never use the complete source image as the final slide background or rasterize a text-bearing card.
- Preserve semantic connector topology. A closed loop, curved cycle, merge, or branch must remain visibly connected and directional; do not flatten it into disconnected straight segments.
- Place connector endpoints close to their source and destination boundaries, and verify that every arrowhead remains clearly visible at final render size. A semantically correct but visibly floating arrow is not acceptable.
- Inspect every placed crop at render size. Reject visible rectangular crop edges, incompatible tile backgrounds, clipped effects, and decorative background seams that are not present in the source.
- Preserve stable element and asset IDs across iterations.
- Save each iteration separately and never overwrite an earlier iteration.

## Resolve typography

Apply explicit user typography first. Otherwise select the interaction mode:

- `ask`: ask once for title font, title size, body font, and body size.
- `match-source`: infer the hierarchy from the reference image.
- `default`: use Microsoft YaHei 32 pt for titles and Microsoft YaHei 18 pt for body text.

Treat requests such as "directly proceed," "match the image," or "do not ask" as `match-source`. Record the resolved values in `request.json` and do not ask again during later iterations.

## Route responsibilities

Keep the roles independent:

- Let the Skill Orchestrator manage user interaction, role calls, state transitions, iteration limits, input isolation, and delivery decisions.
- Let the Layout Planner analyze the source and produce layout, crop, and asset specifications or a review patch.
- Let the Visual Reviewer compare the source, render, and structural QA data without modifying the slide or computing the final policy decision.
- Let deterministic scripts validate contracts, process assets, build and render the presentation, verify structure, evaluate review policy, apply patches, and package accepted output.

Do not let the Planner approve its own output or let the Reviewer modify specifications.
A role configuration file does not execute an Agent. The Orchestrator must explicitly open the Reviewer checkpoint, execute the prepared package in a fresh context, finalize the response, evaluate it, and pass the final review gate.

## Execute the workflow

1. Confirm that a readable source image and conversion request exist.
2. Resolve typography and freeze the normalized request.
3. Generate and validate `layout.json`, `crops.json`, and `asset_manifest.json`.
4. Run deterministic asset processing, PPT construction, font audit, rendering, and structural verification in production mode with `run_state.json`.
5. Stop before visual review when a hard structural QA gate fails.
6. Run the Visual Reviewer with only the approved source, render, structural QA, request summary, and provenance inputs. Require an explicit side-by-side check of connector topology, key proportions, crop edges, background seams, and visual depth even when structural QA passes.
7. Calculate scores, issue counts, editability, and policy status with deterministic evaluation code.
8. Apply an approved review patch transactionally to a new iteration when revision is required.
9. Stop after at most three iterations unless the request explicitly changes the limit.
10. Package only the iteration named by a validated delivery decision.

Never describe a structural QA pass as final completion. `run_pipeline.py` returns `deliverable: false` and `visual_review_status: pending`; it proves only that the iteration is structurally reviewable. Before a normal delivery, run `assert_review_gate.py` and require `visual_review_gate: pass`.

## Enforce review and delivery gates

- Treat `critical + recoverable` as revision and `critical + irrecoverable` as failure.
- Require no critical or major issues, all hard QA gates, and the configured score threshold for a normal pass.
- Require every mandatory visual check to pass or be explicitly `not_applicable` with a reason. A failed mandatory check forces revision or failure even when aggregate scores would otherwise pass.
- Reject a review whose Planner and Reviewer share the same context ID.
- Pause in `awaiting_user_acceptance` for a warning candidate and store the approval message hash before producing `pass_with_warnings`.
- Deliver the editable PPT, asset archive, preview, QA report, review report, review evaluation, and delivery decision from the same accepted iteration.
- Record input, specification, asset, tool, renderer, model, prompt, rubric, parameter, and call provenance where required by the current contract.

## Follow the execution contract

Read [references/task-routing.md](references/task-routing.md), [references/content-planning.md](references/content-planning.md), and [references/outline-contract.md](references/outline-contract.md) for P1 tasks. After P1 completes, follow [references/wireframe-planning.md](references/wireframe-planning.md) for P2. Load [references/constrained-reconstruction.md](references/constrained-reconstruction.md) only after current P3.3 approval evidence exists.

Read [references/agent-orchestration.md](references/agent-orchestration.md) before invoking or implementing a deterministic command. Follow its path, output, logging, and exit-code rules.

Read [references/element-classification.md](references/element-classification.md) before choosing native PowerPoint, raster, or SVG representation, and before applying a text-editability exemption.

Read [references/ppt-build-contract.md](references/ppt-build-contract.md) before invoking or modifying the deterministic PptxGenJS builder.

Read [references/rendering-and-qa.md](references/rendering-and-qa.md) before auditing fonts, rendering a PPTX, verifying structural editability, or invoking the single-iteration pipeline.

Read [references/visual-review-rubric.md](references/visual-review-rubric.md) before preparing a Reviewer call or evaluating a visual review. Use `agents/planner.yaml` and `agents/visual_reviewer.yaml` as separate fresh-context role contracts; never continue a Planner conversation as the Reviewer.

Read [references/iteration-and-delivery.md](references/iteration-and-delivery.md) before advancing run state, applying a review patch, recording warning acceptance, creating a delivery decision, or packaging accepted output.

## Run the P5 final gate and live review

P5 uses tools/delivery/p5_delivery_eval.py. The deterministic command never creates a formal delivery on its own; only a trusted live review can authorize the consumer path.

1. python tools/delivery/p5_delivery_eval.py --deterministic --rebuild-p4-evidence --work-root <work> --report <work>/p5-gate.json
   - Runs the D03 deterministic chain (P4 Compatibility View authority, final integrity with real PowerPoint, deck QA, roundtrip, package candidate) and D05/D08 fixtures.
   - Produces delivery-package-candidate/ only: delivery_forbidden = true, formal_decision_sha256 = null.
   - Ends in state live_review_pending. Gate report status = pending_live_evidence; formal_delivery_created = false; does_not_satisfy_adr_040 = true.
2. A live Deck Consistency Review is REQUIRED by ADR-040 before any policy evaluation, decision, or formal packaging. Frozen replays never satisfy it.
3. python tools/delivery/p5_delivery_eval.py --consume-live-review <evidence-package> --work-root <work> --p4-evidence-root <work>/p4-evidence/D03 --dist-root <dist> --output-name <name> --report <work>/p5-final-gate.json
   - Validates ordered input media/purpose/hash bindings, resolved model identity, transport request, raw/finalized response, role/prompt/schema/ledger hashes, fresh context, retries, system prompt, and three contact sheets.
   - Only then: evaluate -> create-decision -> lock-packaging-runtime -> formal package (7 files) -> verify (two-layer hash closure) -> delivered.

Deterministic state must stop at live_review_pending with Decision = absent and Formal Dist = absent. Packaging is a pure function: same inputs + same runtime lock -> identical ZIP bytes; a packaging runtime fingerprint mismatch stops delivery. The delivered PPTX is byte-identical to the P4 candidate deck.
