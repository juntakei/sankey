"""#!/usr/bin/env python3
"""

"""Colorful demo renderer for the multi-segment Sankey pipeline.

Usage (from repo root):
  PYTHONPATH=. python scripts/demo_render_color.py input.json out.svg [factor] [color_mode] [show_legend]

 - factor: optional float 0..1 controlling fraction of node height used by links (default 1.0)
 - color_mode: optional, "per_segment" (default) or "per_item"
 - show_legend: optional, "true" (default) or "false" to hide the legend

Example:
  PYTHONPATH=. python scripts/demo_render_color.py example_multi_segments.json out.svg 1.0 per_item true
"""
import os
import sys
import math
from collections import defaultdict

# ensure repo root is on sys.path if running from elsewhere
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sankey_pipeline import (
    load_input,
    build_internal_graph,
    compute_node_values,
    group_by_layer,
    barycenter_ordering,
    compute_positions,
)

# We'll call into these internal helpers from sankey_pipeline for thickness/stacking
import sankey_pipeline as sp

PALETTE = [
    "#1f77b4",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#d62728",  # red
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#e377c2",  # pink
    "#7f7f7f",  # gray
    "#bcbd22",  # olive
    "#17becf",  # cyan
]


def parse_bool(s: str, default: bool = True) -> bool:
    if s is None:
        return default
    s = str(s).strip().lower()
    if s in ("1", "true", "t", "yes", "y", "on"):
        return True
    if s in ("0", "false", "f", "no", "n", "off"):
        return False
    return default


def assign_colors(layer_map, nodes, mode: str = "per_segment"):
    node_by_id = {n['id']: n for n in nodes}
    dummy_color = "#cccccc"

    if mode == "per_item":
        node_color = {}
        non_dummy_nodes = [n for n in nodes if not n.get("dummy")]
        for i, n in enumerate(non_dummy_nodes):
            node_color[n['id']] = PALETTE[i % len(PALETTE)]
        for n in nodes:
            if n.get("dummy"):
                node_color[n['id']] = dummy_color
            elif n['id'] not in node_color:
                node_color[n['id']] = PALETTE[len(node_color) % len(PALETTE)]
        used_segs = sorted(set(layer_map.values()))
        seg_to_color = {seg: PALETTE[i % len(PALETTE)] for i, seg in enumerate(used_segs)}
        return seg_to_color, node_color

    used = set()
    for nid, seg in layer_map.items():
        used.add(seg)
    used_sorted = sorted(list(used))
    seg_to_color = {}
    for i, seg in enumerate(used_sorted):
        seg_to_color[seg] = PALETTE[i % len(PALETTE)]
    node_color = {}
    for nid, seg in layer_map.items():
        n = node_by_id.get(nid, {})
        if n.get('dummy'):
            node_color[nid] = dummy_color
        else:
            node_color[nid] = seg_to_color.get(seg, PALETTE[0])
    return seg_to_color, node_color


def render_color_svg(nodes, links, positions, sizes, layer_map,
                     filename="demo_multi_segment_color.svg", width=1000, height=700,
                     factor: float = 1.0, color_mode: str = "per_segment", show_legend: bool = True):
    """Render a colorful SVG with gradient-filled ribbons for links using color_mode."""
    seg_to_color, node_color = assign_colors(layer_map, nodes, mode=color_mode)

    # compute thickness and stacked offsets using pipeline helpers
    thickness_map = sp._compute_link_thicknesses(links, sizes, factor=factor)
    link_pos_map = sp._stack_links_by_node(links, positions, sizes, thickness_map, center_stacks=True)

    def esc(s: str) -> str:
        return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") if s else "")

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg.append('<defs>')

    # create gradient defs for each link, using node_color for stops
    for idx, l in enumerate(links):
        s = l['source']
        t = l['target']
        if s not in positions or t not in positions:
            continue
        x1, y1 = positions[s]
        w1, h1 = sizes.get(s, (10, 10))
        x2, y2 = positions[t]
        w2, h2 = sizes.get(t, (10, 10))
        start_x = x1 + w1 / 2 if (x2 >= x1) else x1 - w1 / 2
        end_x = x2 - w2 / 2 if (x2 >= x1) else x2 + w2 / 2
        grad_id = f"g{idx}"
        color1 = node_color.get(s, PALETTE[0])
        color2 = node_color.get(t, PALETTE[0])
        svg.append(
            f'<linearGradient id="{grad_id}" gradientUnits="userSpaceOnUse" x1="{start_x:.2f}" y1="{y1:.2f}" x2="{end_x:.2f}" y2="{y2:.2f}">'
        )
        svg.append(f'  <stop offset="0%" stop-color="{color1}" stop-opacity="0.95"/>')
        svg.append(f'  <stop offset="100%" stop-color="{color2}" stop-opacity="0.95"/>')
        svg.append('</linearGradient>')

    svg.append('</defs>')
    svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="white"/>')

    # draw ribbons with gradient fill
    for idx, l in enumerate(links):
        s = l['source']
        t = l['target']
        if s not in positions or t not in positions:
            continue
        lp = link_pos_map.get(idx)
        if not lp or 's_top' not in lp or 't_top' not in lp:
            continue

        s_x, s_yc = positions[s]
        t_x, t_yc = positions[t]
        s_w, s_h = sizes.get(s, (10, 10))
        t_w, t_h = sizes.get(t, (10, 10))
        start_x = s_x + s_w / 2 if (t_x >= s_x) else s_x - s_w / 2
        end_x = t_x - t_w / 2 if (t_x >= s_x) else t_x + t_w / 2

        s_top = lp['s_top']
        s_bot = lp['s_bot']
        t_top = lp['t_top']
        t_bot = lp['t_bot']

        dx = (end_x - start_x) * 0.3
        c1x = start_x + dx
        c2x = end_x - dx

        top_path = f'M {start_x:.2f},{s_top:.2f} C {c1x:.2f},{s_top:.2f} {c2x:.2f},{t_top:.2f} {end_x:.2f},{t_top:.2f}'
        bottom_path = f'L {end_x:.2f},{t_bot:.2f} C {c2x:.2f},{t_bot:.2f} {c1x:.2f},{s_bot:.2f} {start_x:.2f},{s_bot:.2f} Z'

        grad_id = f"g{idx}"
        svg.append(f'<path d="{top_path} {bottom_path}" fill="url(#{grad_id})" stroke="none" opacity="0.95"/>')

    # draw nodes on top
    node_by_id = {n['id']: n for n in nodes}
    for nid, (x, y) in positions.items():
        w, h = sizes.get(nid, (10, 10))
        rx = x - w / 2
        ry = y - h / 2
        node = node_by_id.get(nid, {})
        if node.get('dummy'):
            svg.append(f'<rect x="{rx:.2f}" y="{ry:.2f}" width="{w:.2f}" height="{h:.2f}" fill="#efefef" stroke="#bbb" stroke-dasharray="2,2"/>')
        else:
            color = node_color.get(nid, PALETTE[0])
            svg.append(f'<rect x="{rx:.2f}" y="{ry:.2f}" width="{w:.2f}" height="{h:.2f}" rx="3" fill="{color}" stroke="#222" stroke-opacity="0.15"/>')
            label = node.get('label') or nid
            svg.append(f'<text x="{x + w / 2 + 8:.2f}" y="{y + 4:.2f}" font-family="sans-serif" font-size="12" fill="#111">{esc(label)}</text>')

    # legend (optional)
    if show_legend:
        legend_x = width - 260
        legend_y = 20
        svg.append(f'<g class="legend" transform="translate({legend_x},{legend_y})">')
        svg.append('<text x="0" y="0" font-family="sans-serif" font-size="13" fill="#111">Segments / Items</text>')
        y_off = 18
        if color_mode == "per_item":
            shown = 10
            non_dummy_nodes = [n for n in nodes if not n.get("dummy")]
            for n in non_dummy_nodes[:shown]:
                col = node_color.get(n['id'], PALETTE[0])
                svg.append(f'<rect x="0" y="{y_off - 12}" width="14" height="12" fill="{col}" stroke="#444" stroke-opacity="0.2"/>')
                svg.append(f'<text x="22" y="{y_off - 2}" font-family="sans-serif" font-size="12" fill="#111">{esc(n.get("label") or n["id"])}</text>')
                y_off += 18
        else:
            for seg_idx in sorted(seg_to_color.keys()):
                col = seg_to_color[seg_idx]
                svg.append(f'<rect x="0" y="{y_off - 12}" width="14" height="12" fill="{col}" stroke="#444" stroke-opacity="0.2"/>')
                svg.append(f'<text x="22" y="{y_off - 2}" font-family="sans-serif" font-size="12" fill="#111">Segment {seg_idx}</text>')
                y_off += 18
        svg.append('</g>')

    svg.append("</svg>")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))
    print(f"Wrote {filename}")


def render_color_svg_wrapper(nodes, links, positions, sizes, layer_map,
                             filename="demo_multi_segment_color.svg", width=1000, height=700,
                             factor: float = 1.0, color_mode: str = "per_segment", show_legend: bool = True):
    # wrapper to call render_color_svg with color_mode available in scope for legend block
    # (keeps compatibility with existing function name if needed)
    render_color_svg(nodes, links, positions, sizes, layer_map,
                     filename=filename, width=width, height=height,
                     factor=factor, color_mode=color_mode, show_legend=show_legend)


def run_color_demo(input_path: str, output_svg: str = "demo_multi_segment_color.svg",
                   factor: float = 1.0, color_mode: str = "per_segment", show_legend: bool = True):
    nodes, links, segments = load_input(input_path)
    new_nodes, new_links, layer_map = build_internal_graph(nodes, links, segments)
    node_vals = compute_node_values(new_nodes, new_links)
    layers = group_by_layer(new_nodes, layer_map)
    ordering = barycenter_ordering(layers, new_links, iterations=2)
    positions, sizes = compute_positions(layers, ordering, node_vals, width=1200, height=700)
    render_color_svg(new_nodes, new_links, positions, sizes, layer_map,
                     filename=output_svg, width=1200, height=700,
                     factor=factor, color_mode=color_mode, show_legend=show_legend)


if __name__ == "__main__":
    inp = sys.argv[1] if len(sys.argv) > 1 else "example_multi_segments.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "demo_multi_segment_color.svg"
    factor = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    color_mode = sys.argv[4] if len(sys.argv) > 4 else "per_segment"
    show_legend = parse_bool(sys.argv[5], default=True) if len(sys.argv) > 5 else True
    if color_mode not in ("per_segment", "per_item"):
        print("color_mode must be 'per_segment' or 'per_item'. Using 'per_segment'.")
        color_mode = "per_segment"
    run_color_demo(inp, out, factor=factor, color_mode=color_mode, show_legend=show_legend)
