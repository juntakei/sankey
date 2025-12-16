# sankey_pipeline.py
"""
Basic Sankey pipeline for multi-segment layouts.
This module integrates the existing sankey_multi.split_long_links helper and
provides a minimal layout (single-pass barycenter ordering + stacking) and an
SVG renderer used by the demo script.

Updated to render links as filled ribbons whose widths encode link values
and which are stacked inside nodes to prevent overlap.

Link width scaling may be controlled by `link_width_factor` (0..1) so the
sum of link widths per node becomes a fraction of the node height.
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

    q = deque()
    for nid in nodes_ids:
        if indeg.get(nid, 0) == 0:
            q.append(nid)
            if layer_map[nid] is None:
                layer_map[nid] = 0

    while q:
        u = q.popleft()
        u_layer = layer_map.get(u, 0) or 0
        for v in adj[u]:
            cur = layer_map.get(v)
            candidate = u_layer + 1
            if cur is None or candidate > cur:
                layer_map[v] = candidate
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)

    for k in list(layer_map.keys()):
        if layer_map[k] is None:
            layer_map[k] = 0

    min_layer = min(layer_map.values()) if layer_map else 0
    if min_layer != 0:
        for k in layer_map:
            layer_map[k] -= min_layer

    return {k: int(v) for k, v in layer_map.items()}


def build_internal_graph(nodes: List[Dict], links: List[Dict], segments: Optional[List[str]] = None) -> Tuple[List[Dict], List[Dict], Dict[str, int]]:
    layer_map = infer_layers(nodes, links, segments)
    nodes_copy = [dict(n) for n in nodes]
    for n in nodes_copy:
        if n['id'] in layer_map:
            n['segment'] = layer_map[n['id']]
    new_nodes, new_links = split_long_links(nodes_copy, links, segments)
    final_layer_map: Dict[str, int] = {}
    for n in new_nodes:
        seg = n.get('segment', None)
        if isinstance(seg, int):
            final_layer_map[n['id']] = seg
    return new_nodes, new_links, final_layer_map


def compute_node_values(nodes: List[Dict], links: List[Dict]) -> Dict[str, float]:
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
            s = 0.0
            c = 0
            for nb in neighbors:
                for lidx, lst in order.items():
                    if nb in lst:
                        pos = lst.index(nb)
                        s += pos
                        c += 1
                        break
            weights[nid] = (s / c) if c else None
        with_b = [(nid, weights[nid]) for nid in ids]
        has = [x for x in with_b if x[1] is not None]
        nothas = [x for x in with_b if x[1] is None]
        has.sort(key=lambda x: x[1])
        new_order = [x[0] for x in has] + [x[0] for x in nothas]
        order[layer_idx] = new_order

    layer_indices = sorted(order.keys())
    for _ in range(iterations):
        for li in layer_indices[1:]:
            barycenter(li, upward=True)
        for li in reversed(layer_indices[:-1]):
            barycenter(li, upward=False)
    return order


def compute_positions(layers: Dict[int, List[Dict]], ordering: Dict[int, List[str]], node_values: Dict[str, float],
                      width: int = 800, height: int = 600, node_width: int = 20, layer_padding: int = 100,
                      node_padding: int = 8) -> Tuple[Dict[str, Tuple[float, float]], Dict[str, Tuple[float, float]]]:
    num_layers = max(layers.keys()) + 1 if layers else 1
    total_width = width - 40
    if num_layers > 1:
        layer_xs = {i: 20 + i * (total_width / (num_layers - 1)) for i in range(num_layers)}
    else:
        layer_xs = {0: width / 2}

    positions = {}
    sizes = {}

    for li, nodes_in_layer in layers.items():
        ordered_ids = ordering.get(li, [n['id'] for n in nodes_in_layer])
        vals = [node_values.get(nid, 1.0) for nid in ordered_ids]
        total_val = sum(vals) if vals else 1.0
        avail_height = height - 40
        min_node_h = 6
        raw_heights = [max(min_node_h, (v / total_val) * (avail_height * 0.6)) for v in vals]
        y = 20
        for nid, h in zip(ordered_ids, raw_heights):
            x = layer_xs.get(li, 20)
            positions[nid] = (x, y + h / 2)
            sizes[nid] = (node_width, h)
            y += h + node_padding

    return positions, sizes


# --------------------------
# New helpers for ribbon drawing
# --------------------------

def _compute_link_thicknesses(links: List[Dict], sizes: Dict[str, Tuple[float, float]], factor: float = 1.0,
                              min_thickness: float = 1.0) -> Dict[int, float]:
    """
    Compute a pixel thickness for each link (keyed by link index) such that link thicknesses
    are proportional to link values and the sum of thicknesses per node is approximately
    `factor * node_height`.

    Algorithm:
    - For each node compute sum_out_values and sum_in_values of link values.
    - For nodes with non-zero sums, compute scale_out = (node_height * factor) / sum_out_values
      and scale_in = (node_height * factor) / sum_in_values.
    - For each link, derive its thickness by taking the average of the source-scale and target-scale:
       t = v * avg(scale_out_source, scale_in_target)
      or using whichever sides are available.
    - Enforce a minimum thickness.
    """
    if not links:
        return {}
    # compute per-node sums
    sum_out = defaultdict(float)
    sum_in = defaultdict(float)
    for l in links:
        v = l.get('value', 0.0)
        sum_out[l['source']] += v
        sum_in[l['target']] += v

    # per-node scales
    scale_out = {}
    scale_in = {}
    for nid, (w, h) in sizes.items():
        # node height in pixels
        node_h = h
        so = sum_out.get(nid, 0.0)
        si = sum_in.get(nid, 0.0)
        if so > 0:
            scale_out[nid] = (node_h * factor) / so
        if si > 0:
            scale_in[nid] = (node_h * factor) / si

    # fallback global scale if neither side available for a link
    # use a conservative small scale relative to median node height
    median_h = 40.0
    try:
        median_h = sorted([h for (w, h) in sizes.values()])[len(sizes)//2]
    except Exception:
        pass
    default_scale = (median_h * factor) / max(1.0, max((l.get('value', 0.0) for l in links), default=1.0))

    thickness = {}
    for i, l in enumerate(links):
        v = l.get('value', 0.0)
        s_src = scale_out.get(l['source'])
        s_tgt = scale_in.get(l['target'])
        if s_src is not None and s_tgt is not None:
            s = (s_src + s_tgt) / 2.0
        elif s_src is not None:
            s = s_src
        elif s_tgt is not None:
            s = s_tgt
        else:
            s = default_scale
        t = max(min_thickness, v * s)
        thickness[i] = t
    return thickness


def _stack_links_by_node(links: List[Dict], positions: Dict[str, Tuple[float, float]], sizes: Dict[str, Tuple[float, float]],
                         thickness_map: Dict[int, float], center_stacks: bool = True) -> Dict[int, Dict[str, float]]:
    out_lists = defaultdict(list)
    in_lists = defaultdict(list)
    for idx, l in enumerate(links):
        out_lists[l['source']].append(idx)
        in_lists[l['target']].append(idx)

    link_positions = {}
    # outgoing stacks
    for nid, idxs in out_lists.items():
        if nid not in positions or nid not in sizes:
            continue
        x, yc = positions[nid]
        w, h = sizes[nid]
        top = yc - h / 2
        # compute total thickness for this node's outgoing links
        total_t = sum(thickness_map.get(idx, 0.0) for idx in idxs)
        cur = top
        if center_stacks and total_t < h:
            cur = top + (h - total_t) / 2.0
        for idx in idxs:
            t = thickness_map.get(idx, 1.0)
            s_top = cur
            s_bot = cur + t
            if idx not in link_positions:
                link_positions[idx] = {}
            link_positions[idx]['s_top'] = s_top
            link_positions[idx]['s_bot'] = s_bot
            link_positions[idx]['thickness'] = t
            cur = s_bot
    # incoming stacks
    for nid, idxs in in_lists.items():
        if nid not in positions or nid not in sizes:
            continue
        x, yc = positions[nid]
        w, h = sizes[nid]
        top = yc - h / 2
        total_t = sum(thickness_map.get(idx, 0.0) for idx in idxs)
        cur = top
        if center_stacks and total_t < h:
            cur = top + (h - total_t) / 2.0
        for idx in idxs:
            t = thickness_map.get(idx, 1.0)
            t_top = cur
            t_bot = cur + t
            if idx not in link_positions:
                link_positions[idx] = {}
            link_positions[idx]['t_top'] = t_top
            link_positions[idx]['t_bot'] = t_bot
            link_positions[idx]['thickness'] = t
            cur = t_bot
    return link_positions


def render_svg(nodes: List[Dict], links: List[Dict], positions: Dict[str, Tuple[float, float]], sizes: Dict[str, Tuple[float, float]],
               layer_map: Dict[str, int], filename: str = 'output.svg', width: int = 800, height: int = 600,
               link_width_factor: float = 1.0):
    def esc(s: str) -> str:
        return (s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;') if s else '')

    node_by_id = {n['id']: n for n in nodes}

    # compute thickness map using sizes and factor
    thickness_map = _compute_link_thicknesses(links, sizes, factor=link_width_factor)
    link_pos_map = _stack_links_by_node(links, positions, sizes, thickness_map)

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg.append('<style> .node {fill:#1f77b4; stroke:#000; stroke-width:0.5;} .label{font:12px sans-serif; fill:#000;} .link{fill-opacity:0.6; stroke:none;} </style>')

    # draw links first so nodes are on top
    for i, l in enumerate(links):
        s = l['source']
        t = l['target']
        if s not in positions or t not in positions:
            continue
        lp = link_pos_map.get(i)
        if not lp or 's_top' not in lp or 't_top' not in lp:
            x1, y1 = positions[s]
            x2, y2 = positions[t]
            start_x = x1 + sizes.get(s, (10,10))[0]/2
            end_x = x2 - sizes.get(t,(10,10))[0]/2
            stroke_w = thickness_map.get(i, 1.0)
            path = f'M {start_x:.2f},{y1:.2f} C {start_x + (end_x-start_x)*0.3:.2f},{y1:.2f} {end_x - (end_x-start_x)*0.3:.2f},{y2:.2f} {end_x:.2f},{y2:.2f}'
            svg.append(f'<path d="{path}" class="link" stroke="#888" stroke-width="{stroke_w:.2f}" fill="none" stroke-opacity="0.8" />')
            continue

        s_x, s_yc = positions[s]
        t_x, t_yc = positions[t]
        s_w, s_h = sizes.get(s, (10,10))
        t_w, t_h = sizes.get(t, (10,10))

        start_x = s_x + s_w/2 if (t_x >= s_x) else s_x - s_w/2
        end_x = t_x - t_w/2 if (t_x >= s_x) else t_x + t_w/2

        s_top = lp['s_top']
        s_bot = lp['s_bot']
        t_top = lp['t_top']
        t_bot = lp['t_bot']

        dx = (end_x - start_x) * 0.3
        c1x = start_x + dx
        c2x = end_x - dx

        top_path = f'M {start_x:.2f},{s_top:.2f} C {c1x:.2f},{s_top:.2f} {c2x:.2f},{t_top:.2f} {end_x:.2f},{t_top:.2f}'
        bottom_path = f'L {end_x:.2f},{t_bot:.2f} C {c2x:.2f},{t_bot:.2f} {c1x:.2f},{s_bot:.2f} {start_x:.2f},{s_bot:.2f} Z'

        svg.append(f'<path d="{top_path} {bottom_path}" fill="#dcdcdc" stroke="none" opacity="0.9"/>')

    # draw nodes
    for nid, (x, y) in positions.items():
        w, h = sizes.get(nid, (10, 10))
        rx = x - w/2
        ry = y - h/2
        node = node_by_id.get(nid, {})
        if node.get('dummy'):
            svg.append(f'<rect x="{rx:.2f}" y="{ry:.2f}" width="{w:.2f}" height="{h:.2f}" fill="#ccc" stroke="#666" stroke-dasharray="2,2"/>')
        else:
            svg.append(f'<rect x="{rx:.2f}" y="{ry:.2f}" width="{w:.2f}" height="{h:.2f}" class="node"/>')
            label = node.get('label') or nid
            svg.append(f'<text x="{x + w/2 + 6:.2f}" y="{y + 4:.2f}" class="label">{esc(label)}</text>')

    svg.append('</svg>')

    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(svg))
