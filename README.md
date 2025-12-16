# Sankey (multi-segment support)

This repository implements a lightweight Sankey diagram pipeline with support for multi-segment (multi-column) layouts, long-span link splitting, and a small demo renderer that produces SVG output.

This README addition documents the new multi-segment features, usage examples, demo commands, test instructions, and suggested commit/PR text for the feature branch.

## What I added

- sankey_schema.json — JSON Schema for the new multi-segment input format.
- sankey_multi.py — helper to split long-span links into adjacent-segment chains (dummy nodes).
- sankey_pipeline.py — pipeline + layout including:
  - layer inference (when `segments` is omitted),
  - integration with `split_long_links`,
  - a simple barycenter ordering,
  - node stacking and position computation,
  - ribbon rendering support where link width encodes value.
- scripts/demo_render.py — simple demo runner that creates a basic SVG.
- scripts/demo_render_color.py — colorful demo runner that:
  - draws gradient-filled ribbons,
  - supports `link_width_factor` to control how link widths scale relative to node heights,
  - supports two color modes:
    - `per_segment` (default): nodes colored by segment/column,
    - `per_item`: each non-dummy node receives its own color from the palette.
- Example JSON files:
  - example_multi_segments.json
  - example_span.json
  - legacy_two_column_example.json
- Unit tests:
  - tests/test_split_long_links.py (covers splitting behavior and uniqueness)

## Multi-segment input format

The new input JSON supports:
- `segments` (optional): ordered array of segment names (left → right).
- `nodes`: array of objects with at least `id`. Optional `label`, `segment` (index or name), `value`.
- `links`: array of `{ source, target, value, ... }`.

Backward compatibility:
- The parser accepts a legacy two-column format (`sources`, `targets`, `links`) and converts it to `nodes`/`links` with `segments = ["left","right"]`.
- If `segments` is omitted and nodes don't provide `segment`, the pipeline attempts to infer layers from topology.

See `sankey_schema.json` for more details.

## Demo usage

From the repository root (so Python can import local modules):

- Basic color demo (per-segment coloring, factor 1.0):
  PYTHONPATH=. python scripts/demo_render_color.py example_multi_segments.json demo_multi_segment_color.svg 1.0 per_segment

- Per-item coloring, 50% factor:
  PYTHONPATH=. python scripts/demo_render_color.py example_multi_segments.json demo_multi_segment_color.svg 0.5 per_item

- Run the simple demo (no color):
  PYTHONPATH=. python scripts/demo_render.py example_multi_segments.json demo_multi_segment.svg

Open the generated `.svg` files in your browser to inspect the results.

## `link_width_factor` (factor)

- The optional `factor` (0..1) controls how link widths map to node heights.
  - `factor = 1.0` — the sum of link widths per node will be approximately the node height (averaged between source/target).
  - `factor = 0.5` — the sum will be ~50% of the node height, useful for dense graphs.
- This is a practical compromise (each link participates in two nodes), so widths are computed using per-node scales and then averaged for consistency.
- If you want exact equality on all nodes simultaneously, we can add a small iterative solver — ask if you'd like that.

## Legend
- Legend will be shown by default. If you want not to show legend, add "false" to the command.
- sample $ python scripts/demo_render_color.py example_multi_segments.json demo.svg 0.9 per_item false

## Tests

- Install pytest (if not already):
  python -m pip install pytest

- Run tests from repo root:
  PYTHONPATH=. pytest -q

The tests currently cover `split_long_links` behavior.

## Developer notes / integration points

- To integrate into your existing rendering pipeline:
  1. Parse input JSON (or validate against `sankey_schema.json`).
  2. Call `build_internal_graph(nodes, links, segments)` (returns augmented nodes/links and layer map).
  3. Compute `node_vals = compute_node_values(nodes, links)`.
  4. Build `layers = group_by_layer(nodes, layer_map)`.
  5. Compute `ordering = barycenter_ordering(layers, links, iterations=...)`.
  6. Compute `positions, sizes = compute_positions(layers, ordering, node_vals, ...)`.
  7. Render: either `render_svg(...)` (simple grayscale ribbons) or use the color demo to render gradient ribbons and control `link_width_factor` and color mode.

- Dummy nodes inserted by splitting are marked with `"dummy": true`. Exclude their labels in final user-facing renderings if desired.

## Files to review

- sankey_schema.json
- sankey_multi.py
- sankey_pipeline.py
- scripts/demo_render.py
- scripts/demo_render_color.py
- example_multi_segments.json
- tests/test_split_long_links.py


  Checklist:
  - [x] schema & examples
  - [x] split_long_links implementation + tests
  - [x] pipeline + basic layout
  - [x] ribbon renderer and colorful demo
  - [ ] iterate on crossing minimization (follow-up)
  - [ ] optional iterative thickness solver (follow-up)

