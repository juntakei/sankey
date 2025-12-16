"""
Basic Sankey pipeline for multi-segment layouts.
This module integrates the existing sankey_multi.split_long_links helper and
provides a minimal layout (single-pass barycenter ordering + stacking) and an
SVG renderer used by the demo script.

This is intentionally lightweight and dependency-free: it generates an SVG
string directly so it works without adding libraries.
"""

from typing import List, Dict, Optional, Tuple
import json
import math
from collections import defaultdict, deque

# import the helper we added earlier
from sankey_multi import split_long_links


def load_input(path: str) -> Tuple[List[Dict], List[Dict], Optional[List[str]]]:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # support legacy two-column format
    if 'sources' in data and 'targets' in data and 'links' in data:
        segments = ["left", "right"]
        nodes = []
        for s in data['sources']:
            node = dict(s)
            node.setdefault('segment', 0)
            nodes.append(node)
        for t in data['targets']:
            node = dict(t)
            node.setdefault('segment', 1)
            nodes.append(node)
        links = data['links']
        return nodes, links, segments

    nodes = data.get('nodes', [])
    links = data.get('links', [])
    segments = data.get('segments', None)
    return nodes, links, segments


def infer_layers(nodes: List[Dict], links: List[Dict], segments: Optional[List[str]] = None) -> Dict[str, int]:
    """Return a map node_id -> layer index.
    If nodes have explicit 'segment' use that (resolving names via segments list).
    Otherwise try to infer layers by topological layering (min distance from sources).
    """
    node_map = {n['id']: n for n in nodes}
    layer_map: Dict[str, Optional[int]] = {}

    # first pass: use explicit segment if present
    for n in nodes:
        seg = n.get('segment', None)
        if seg is None:
            layer_map[n['id']] = None
        else:
            if isinstance(seg, int):
                layer_map[n['id']] = seg
            elif isinstance(seg, str) and segments is not None:
                try:
                    layer_map[n['id']] = segments.index(seg)
                except ValueError:
                    layer_map[n['id']] = None
            else:
                layer_map[n['id']] = None

    # if all layers known, return
    if all(v is not None for v in layer_map.values()):
        return {k: int(v) for k, v in layer_map.items()}

    # build adjacency and indegree for topo
    adj = defaultdict(list)
    indeg = defaultdict(int)
    nodes_ids = list(node_map.keys())
    for l in links:
        s = l['source']
        t = l['target']
        if s in node_map and t in node_map:
            adj[s].append(t)
            indeg[t] += 1
            indeg.setdefault(s, indeg.get(s, 0))

    # nodes with indeg 0 are sources — layer 0 (if not already set)
    q = deque()
    for nid in nodes_ids:
        if indeg.get(nid, 0) == 0:
            q.append(nid)
            if layer_map[nid] is None:
                layer_map[nid] = 0

    # BFS-like propagation assigning layer = max(parent_layer)+1
    while q:
        u = q.popleft()
        u_layer = layer_map.get(u, 0) or 0
        for v in adj[u]:
            # set tentative layer for v
            cur = layer_map.get(v)
            candidate = u_layer + 1
            if cur is None or candidate > cur:
                layer_map[v] = candidate
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)

    # fallback: any remaining None -> 0
    for k in list(layer_map.keys()):
        if layer_map[k] is None:
            layer_map[k] = 0

    # normalize so smallest layer is 0
    min_layer = min(layer_map.values()) if layer_map else 0
    if min_layer != 0:
        for k in layer_map:
            layer_map[k] -= min_layer

    return {k: int(v) for k, v in layer_map.items()}


def build_internal_graph(nodes: List[Dict], links: List[Dict], segments: Optional[List[str]] = None) -> Tuple[List[Dict], List[Dict], Dict[str, int]]:
    """Split long links and return augmented nodes/links and computed layer map."""
    # first get layer hints from nodes
    layer_map = infer_layers(nodes, links, segments)
    # annotate nodes with resolved integer 'segment' for split_long_links
    nodes_copy = [dict(n) for n in nodes]
    for n in nodes_copy:
        if n['id'] in layer_map:
            n['segment'] = layer_map[n['id']]
    new_nodes, new_links = split_long_links(nodes_copy, links, segments)
    # recompute layer_map including dummy nodes
    final_layer_map: Dict[str, int] = {}
    for n in new_nodes:
        seg = n.get('segment', None)
        if isinstance(seg, int):
            final_layer_map[n['id']] = seg
    return new_nodes, new_links, final_layer_map


def compute_node_values(nodes: List[Dict], links: List[Dict]) -> Dict[str, float]:
    """Compute node total value = max(sum(in), sum(out)) as a layout heuristic."""
    in_sum = defaultdict(float)
    out_sum = defaultdict(float)
    for l in links:
        out_sum[l['source']] += l.get('value', 0)
        in_sum[l['target']] += l.get('value', 0)
    vals = {}
    for n in nodes:
        nid = n['id']
        vals[nid] = max(in_sum.get(nid, 0.0), out_sum.get(nid, 0.0), n.get('value', 0.0))
    return vals


def group_by_layer(nodes: List[Dict], layer_map: Dict[str, int]) -> Dict[int, List[Dict]]:
    layers = defaultdict(list)
    for n in nodes:
        lid = layer_map.get(n['id'])
        if lid is None:
            lid = n.get('segment', 0)
        layers[int(lid)].append(n)
    return dict(layers)


def barycenter_ordering(layers: Dict[int, List[Dict]], links: List[Dict], iterations: int = 1) -> Dict[int, List[str]]:
    """Return ordering (list of node ids per layer) after simple barycenter passes.
    We perform top-down then bottom-up passes for 'iterations' times.
    """
    # adjacency maps
    preds = defaultdict(list)
    succs = defaultdict(list)
    for l in links:
        preds[l['target']].append(l['source'])
        succs[l['source']].append(l['target'])

    order = {layer: [n['id'] for n in nodes] for layer, nodes in layers.items()}

    def barycenter(layer_idx: int, upward: bool):
        ids = order[layer_idx]
        weights = {}
        for nid in ids:
            neighbors = preds[nid] if upward else succs[nid]
            if not neighbors:
                weights[nid] = None
                continue
            # compute average index of neighbors in their layer
            s = 0.0
            c = 0
            for nb in neighbors:
                # find neighbor's position
                # find layer of neighbor
                for lidx, lst in order.items():
                    if nb in lst:
                        pos = lst.index(nb)
                        s += pos
                        c += 1
                        break
            weights[nid] = (s / c) if c else None
        # sort by barycenter where present, preserving relative order for None
        with_b = [(nid, weights[nid]) for nid in ids]
        # nodes with None barycenter keep their order but placed after those with values
        has = [x for x in with_b if x[1] is not None]
        nothas = [x for x in with_b if x[1] is None]
        has.sort(key=lambda x: x[1])
        new_order = [x[0] for x in has] + [x[0] for x in nothas]
        order[layer_idx] = new_order

    layer_indices = sorted(order.keys())
    for _ in range(iterations):
        # top-down
        for li in layer_indices[1:]:
            barycenter(li, upward=True)
        # bottom-up
        for li in reversed(layer_indices[:-1]):
            barycenter(li, upward=False)
    return order


def compute_positions(layers: Dict[int, List[Dict]], ordering: Dict[int, List[str]], node_values: Dict[str, float],
                      width: int = 800, height: int = 600, node_width: int = 20, layer_padding: int = 100,
                      node_padding: int = 8) -> Tuple[Dict[str, Tuple[float, float]], Dict[str, Tuple[float, float]]]:
    """Compute x,y centers and rect sizes for nodes; returns node_positions and node_sizes.
    node_positions: id -> (x_center, y_center)
    node_sizes: id -> (width, height)
    """
    num_layers = max(layers.keys()) + 1 if layers else 1
    # compute x for each layer
    total_width = width - 40
    if num_layers > 1:
        layer_xs = {i: 20 + i * (total_width / (num_layers - 1)) for i in range(num_layers)}
    else:
        layer_xs = {0: width / 2}

    # compute heights per layer stacking
    positions = {}
    sizes = {}

    for li, nodes_in_layer in layers.items():
        ordered_ids = ordering.get(li, [n['id'] for n in nodes_in_layer])
        # compute total value for scaling
        vals = [node_values.get(nid, 1.0) for nid in ordered_ids]
        total_val = sum(vals) if vals else 1.0
        # allocate available height
        avail_height = height - 40
        # determine scaling factor so that sum of node heights + paddings fits avail_height
        # initial naive height: proportional to value with a minimal size
        min_node_h = 6
        raw_heights = [max(min_node_h, (v / total_val) * (avail_height * 0.6)) for v in vals]
        # compute the y positions stacked from top=20
        y = 20
        for nid, h in zip(ordered_ids, raw_heights):
            x = layer_xs.get(li, 20)
            positions[nid] = (x, y + h / 2)
            sizes[nid] = (node_width, h)
            y += h + node_padding

    return positions, sizes


def render_svg(nodes: List[Dict], links: List[Dict], positions: Dict[str, Tuple[float, float]], sizes: Dict[str, Tuple[float, float]],
               layer_map: Dict[str, int], filename: str = 'output.svg', width: int = 800, height: int = 600):
    """Render a very simple SVG: nodes as rects and links as cubic Bezier curves between layer centers."""
    def esc(s: str) -> str:
        return (s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;') if s else '')

    node_by_id = {n['id']: n for n in nodes}

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg.append('<style> .node {fill:#1f77b4; stroke:#000; stroke-width:0.5;} .label{font:12px sans-serif; fill:#000;} .link{fill:none; stroke:#999; stroke-opacity:0.5;} </style>')

    # draw links first so nodes are on top
    for l in links:
        s = l['source']
        t = l['target']
        if s not in positions or t not in positions:
            continue
        x1, y1 = positions[s]
        w1, h1 = sizes.get(s, (10,10))
        x2, y2 = positions[t]
        w2, h2 = sizes.get(t, (10,10))
        # compute left/right edge points
        # if target is to the right, start at x1 + w/2 else x1 - w/2
        start_x = x1 + w1/2 if (x2 >= x1) else x1 - w1/2
        end_x = x2 - w2/2 if (x2 >= x1) else x2 + w2/2
        # control points
        dx = (end_x - start_x) * 0.3
        c1x = start_x + dx
        c1y = y1
        c2x = end_x - dx
        c2y = y2
        stroke_w = max(1.0, math.sqrt(l.get('value', 1.0)))
        path = f'M {start_x:.2f},{y1:.2f} C {c1x:.2f},{c1y:.2f} {c2x:.2f},{c2y:.2f} {end_x:.2f},{y2:.2f}'
        svg.append(f'<path d="{path}" class="link" stroke-width="{stroke_w:.2f}" stroke="#888" />')

    # draw nodes
    for nid, (x, y) in positions.items():
        w, h = sizes.get(nid, (10, 10))
        rx = x - w/2
        ry = y - h/2
        node = node_by_id.get(nid, {})
        cls = 'node'
        # dummy nodes are rendered faintly
        if node.get('dummy'):
            svg.append(f'<rect x="{rx:.2f}" y="{ry:.2f}" width="{w:.2f}" height="{h:.2f}" fill="#ccc" stroke="#666" stroke-dasharray="2,2"/>')
        else:
            svg.append(f'<rect x="{rx:.2f}" y="{ry:.2f}" width="{w:.2f}" height="{h:.2f}" class="node"/>')
            label = node.get('label') or nid
            svg.append(f'<text x="{x + w/2 + 6:.2f}" y="{y + 4:.2f}" class="label">{esc(label)}</text>')

    svg.append('</svg>')

    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(svg))


def run_pipeline(input_path: str, output_svg: str = 'demo_multi_segment.svg'):
    nodes, links, segments = load_input(input_path)
    new_nodes, new_links, layer_map = build_internal_graph(nodes, links, segments)
    # compute node values
    node_vals = compute_node_values(new_nodes, new_links)
    # group by layer
    layers = group_by_layer(new_nodes, layer_map)
    # ordering
    ordering = barycenter_ordering(layers, new_links, iterations=2)
    # positions
    positions, sizes = compute_positions(layers, ordering, node_vals, width=1000, height=600)
    # render
    render_svg(new_nodes, new_links, positions, sizes, layer_map, filename=output_svg, width=1000, height=600)


if __name__ == '__main__':
    import sys
    inp = sys.argv[1] if len(sys.argv) > 1 else 'example_multi_segments.json'
    out = sys.argv[2] if len(sys.argv) > 2 else 'demo_multi_segment.svg'
    run_pipeline(inp, out)