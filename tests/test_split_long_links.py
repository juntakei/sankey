# tests for sankey_multi.split_long_links
import pytest
from sankey_multi import split_long_links

def test_no_split_adjacent():
    nodes = [
        {"id": "A", "segment": 0},
        {"id": "B", "segment": 1}
    ]
    links = [{"source": "A", "target": "B", "value": 5}]
    new_nodes, new_links = split_long_links(nodes, links)
    assert len(new_nodes) == 2
    assert len(new_links) == 1
    assert new_links[0]["source"] == "A" and new_links[0]["target"] == "B"

def test_split_one_intermediate_layer():
    nodes = [
        {"id": "A", "segment": 0},
        {"id": "B", "segment": 2}
    ]
    links = [{"source": "A", "target": "B", "value": 7, "label": "long"}]
    new_nodes, new_links = split_long_links(nodes, links)
    # should create one dummy node and two links
    assert any(n.get("dummy") for n in new_nodes)
    dummies = [n for n in new_nodes if n.get("dummy")]
    assert len(dummies) == 1
    assert len(new_links) == 2
    # both new links must carry original label metadata
    assert all("label" in l and l["label"] == "long" for l in new_links)

def test_preserve_when_missing_layer_info():
    nodes = [
        {"id": "A"},  # no segment
        {"id": "B", "segment": 2}
    ]
    links = [{"source": "A", "target": "B", "value": 1}]
    new_nodes, new_links = split_long_links(nodes, links)
    # no splitting occurs because A has no segment info
    assert len(new_nodes) == 2
    assert len(new_links) == 1

def test_multiple_links_and_uniqueness():
    nodes = [
        {"id": "L1", "segment": 0},
        {"id": "FR1", "segment": 3}
    ]
    links = [
        {"source": "L1", "target": "FR1", "value": 8},
        {"source": "L1", "target": "FR1", "value": 2}
    ]
    new_nodes, new_links = split_long_links(nodes, links)
    dummies = [n for n in new_nodes if n.get("dummy")]
    # should create dummy nodes for both links (unique ids)
    assert len(dummies) == 2
    # resulting link count: each original link -> 3 adjacent edges -> so total 6 new links
    assert len(new_links) == 6