```markdown
# Multi-segment Sankey input (short guide)

The new multi-segment format supports an explicit ordered `segments` array (left-to-right). Each `node` must have a unique `id`; nodes can specify their `segment` either as a 0-based index into `segments` or by segment name. `links` connect `source` -> `target` by node id and must include a numeric `value`.

Long-span links (links connecting nodes that are more than one segment apart) will be internally split into chains of dummy/intermediate nodes — one dummy per intermediate segment — so the layout algorithm operates on adjacent-segment edges only. This preserves visual continuity while enabling standard layer-by-layer ordering heuristics.

Backward compatibility:
- A legacy two-column format (with `sources` and `targets`) will be accepted by the parser and converted automatically to `nodes` + `links` with `segments = ["left","right"]`.
- If `segments` is omitted and nodes don't provide `segment`, the parser will attempt to infer layers from topology (e.g., nodes only referenced as sources placed left, only referenced as targets placed right). For complex graphs automatic inference may require hints (set `segment` on nodes).

Options (parser/layout):
- `options.ordering`: "barycenter" (default), "median", or "preserve".
- `options.segmentKey`: alternate node key to read segment from (default "segment").

Example usage:
- Validate input JSON against `sankey_schema.json`.
- Convert legacy input if necessary.
- Build internal graph, split long links into dummy nodes, perform layer ordering, compute node sizes/positions, emit layout and render.
```