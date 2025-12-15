# Minimal helper to split long-span links into adjacent-layer chains by inserting dummy nodes.
# This module aims to be small and easy to test; later it can be integrated into the full pipeline.

from typing import List, Dict, Tuple, Optional
import itertools

def _get_node_layer(node: Dict, segments: Optional[List[str]]) -> Optional[int]:
    """
    Return integer layer index for node or None if unknown.
    Node['segment'] may be integer or string (segment name).
    """
    seg = node.get("segment", None)
    if seg is None:
        return None
    if isinstance(seg, int):
        return seg
    if isinstance(seg, str):
        if segments is None:
            return None
        try:
            return segments.index(seg)
        except ValueError:
            return None
    return None

def split_long_links(nodes: List[Dict], links: List[Dict], segments: Optional[List[str]] = None
                     ) -> Tuple[List[Dict], List[Dict]]:
    """
    Given nodes and links, split each link that spans >1 layers into a chain of adjacent-layer edges
    by inserting dummy nodes (one dummy per intermediate layer).
    - nodes: list of node dicts (must have 'id')
    - links: list of link dicts with keys 'source', 'target', 'value' (other keys preserved)
    - segments: optional list of segment names (indexes are used when nodes use strings for segment)
    Returns (new_nodes, new_links). Dummy nodes have keys:
      { 'id': '__dummy_{incremental}', 'label': None, 'segment': layer_index, 'dummy': True, 'orig_link': link_index }
    """
    node_map = {n['id']: n for n in nodes}
    # compute node layers
    layer_map = {}
    for n in nodes:
        layer = _get_node_layer(n, segments)
        if layer is not None:
            layer_map[n['id']] = layer

    new_nodes = list(nodes)  # shallow copy
    new_links = []
    dummy_counter = itertools.count(1)

    for li, link in enumerate(links):
        src = link['source']
        tgt = link['target']
        val = link.get('value', 0)
        if src not in node_map or tgt not in node_map:
            # preserve link as-is if nodes missing (parser should validate earlier)
            new_links.append(dict(link))
            continue
        src_layer = layer_map.get(src, None)
        tgt_layer = layer_map.get(tgt, None)

        # If we don't know layers for either end, preserve link as-is.
        if src_layer is None or tgt_layer is None:
            new_links.append(dict(link))
            continue

        if tgt_layer == src_layer or abs(tgt_layer - src_layer) == 1:
            # adjacent layers (or same layer) — no splitting required
            new_links.append(dict(link))
            continue

        # handle directionality: allow links only left-to-right splitting (if right-to-left, preserve as-is)
        # For Sankey we expect left-to-right (increasing layer index). If link is reversed, keep as-is
        if tgt_layer < src_layer:
            # optionally we could reverse; but preserve original for now
            new_links.append(dict(link))
            continue

        # create chain: src -> D(k=src_layer+1) -> ... -> tgt
        prev = src
        # create dummy per intermediate layer
        for layer in range(src_layer + 1, tgt_layer):
            did = f"__dummy_l{src_layer}_{tgt_layer}_{next(dummy_counter)}"
            dummy_node = {
                "id": did,
                "label": None,
                "segment": layer,
                "dummy": True,
                "orig_link_index": li
            }
            new_nodes.append(dummy_node)
            # create link prev -> did
            new_links.append({
                "source": prev,
                "target": did,
                "value": val,
                # carry original metadata if present
                **({k: v for k, v in link.items() if k not in ('source', 'target', 'value')})
            })
            prev = did
        # final connector prev -> tgt
        new_links.append({
            "source": prev,
            "target": tgt,
            "value": val,
            **({k: v for k, v in link.items() if k not in ('source', 'target', 'value')})
        })

    return new_nodes, new_links