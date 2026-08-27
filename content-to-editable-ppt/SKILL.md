---
name: content-to-editable-ppt
description: Turn confirmed content into an editable multi-page PowerPoint, or rebuild one reference image as an editable single slide. Use when a user wants an editable PPT rather than a static image.
---

# Content to Editable PPT

## Choose the route

- Use the multi-page route for a topic, outline, document, or a set of planned slides.
- Use the independent single-slide compatibility route only when the user supplies one reference image to rebuild as editable PowerPoint.

Do not combine the routes or expose internal build stages to the user.

## Multi-page route

1. Read the user materials and propose one concise deck plan: slide order, title, key message, editable text, major editable shapes or charts, and any necessary image placement.
2. Show that combined plan once and wait for explicit confirmation. Incorporate requested changes into a revised plan; do not build before confirmation.
3. After confirmation, create a `deck-build-request.json` with exact inch coordinates and invoke:

   ```powershell
   python content-to-editable-ppt/scripts/run.py `
     --request <deck-build-request.json> `
     --work-dir <new-work-directory> `
     --output-dir <new-output-directory> `
     [--asset-root <asset-directory>] `
     [--node <node.exe>]
   ```

The request must be `confirmation_status: confirmed`. `work-dir` and `output-dir` must be new, separate directories. Supply `asset-root` only when the request uses PNG, JPEG, or SVG assets.

The host owns wording, slide plan, and coordinates. The runtime builds the supplied plan; it does not invent a template, revise content, wait for user input, resume an older run, or consume historical artifacts.

## Content and editability rules

- Keep titles, body text, numbers, formulas, and step labels as native text elements with `content_ref`.
- Keep major cards, connectors, and charts as native PowerPoint objects whenever represented in the plan.
- Use images only for visual material. An image containing required text needs an explicit editability exemption and cannot replace a whole slide.
- Do not let an image overlap native text. Decorative shapes and lines may support text.
- Use only local, hash-verified assets under `asset-root`; do not provide URLs, absolute paths, or paths outside that root.

On success, the multi-page output directory contains exactly two files: an editable `.pptx` and one contact-sheet `.png` preview. If validation, PowerPoint rendering, roundtrip, or QA fails, stop and report the failure; do not publish a partial output.

## Single-slide compatibility route

For one reference image, keep using the established `run_pipeline.py` workflow and its existing Planner, Visual Reviewer, recovery, review gate, warning acceptance, delivery decision, and seven-file delivery contract. Do not route a multi-page request through it, and do not weaken its review or delivery behavior.
