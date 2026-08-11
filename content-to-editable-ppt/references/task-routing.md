# P1 Task Routing

Use this reference before creating a Content-to-PPT planning workspace.

## Routes

- `content_to_ppt`: the user wants a new presentation from a topic or materials.
- `image_to_editable_ppt`: the user wants an existing page design rebuilt directly.
- `needs_clarification`: the supplied materials and requested outcome do not identify either route safely.

Do not infer a route from file extensions. When materials and design images are both present, follow the user's explicit requested outcome. A clarification creates a new route revision and must bind the user's clarification message hash. Image-to-PPT enters `p1_bypassed` and must not create an Outline.

P1 planning itself does not require PowerPoint readiness. Run the Windows and PowerPoint Ready Gate only before entering the reconstruction Runtime.
