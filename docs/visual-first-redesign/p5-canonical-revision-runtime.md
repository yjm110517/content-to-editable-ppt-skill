# Canonical Revision Runtime

Canonical Revision is opt-in (`--revision-contract canonical`). Legacy Revision remains
the default and keeps its separate input profile, prompt, response and Apply path.

## Validation and publication

Prepare, Finalizer, Validate and Apply use the shared byte-bound revision context.
It binds the current Plan, Handoff, Source, Visual Spec, Review/Evaluation and baseline
QA/Runtime artifacts. Evaluation must equal the existing deterministic evaluator's result.
Finalizer validates the in-memory revised Plan and Compiler candidate but only publishes
the finalized Patch. Apply publishes Plan, Patch, Diff and three Compiler artifacts in one
directory rename. On Windows, rename rejects even an empty existing destination.

All read input bytes are rechecked before publication. An existing next directory is never
deleted or overwritten. No Legacy run_state is required or changed by Canonical Apply.
The independent Deep Diff reports actual paths, before/after values, field presence and
Target/Linked/Locked classification. Unauthorized changes fail validation.

## Consecutive revisions

Initial Finalizer produces Plan 1.2. Valid Plan 1.0/1.1 baselines can also be revised;
successful revisions always output Plan 1.2 and increment page.iteration by one.

For the first revision, Finalizer writes `iterations/01/revision_patch.json`.
Apply copies those exact bytes into `iterations/02/revision_patch.json`, which is now
the **incoming** patch referenced by Plan 02 provenance. It must not be overwritten.
The next Finalizer therefore writes `iterations/02/revision_patch.to-03.json`.
Use that outgoing file as Apply's `--patch`; iteration 03 again stores its incoming copy
as `revision_patch.json`. The same naming rule applies to later revisions.

## Tests versus Live evidence

The fixtures under tests/runtime explicitly distinguish synthetic QA from actual PowerPoint
QA. The P5 PowerPoint smoke uses a deterministic Planner response and real baseline/revised
PowerPoint pipelines; it is not Fresh Planner Live evidence.

Live closure additionally requires a new isolated model call with the frozen System Prompt,
metadata, all ten complete inputs including the image, and a truthful host-generated call
record 1.4. Configured sampling intent is recorded separately from per-parameter observation;
an unavailable value must use `host_not_exposed` and must not contain a guessed value.
Sampling metadata availability is not a Live gate. Fresh context, ordered input delivery,
image modality, unchanged raw-response bytes and successful status remain strict evidence.
No evidence or phase status may claim Live PASS merely because automated tests or
PowerPoint smokes pass.

This document describes the runtime contract, not a P5 closure declaration.
