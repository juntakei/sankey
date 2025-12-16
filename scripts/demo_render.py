#!/usr/bin/env python3
"""
Demo script to render the provided example_multi_segments.json into an SVG using the
pipeline implemented in sankey_pipeline.py
"""
from sankey_pipeline import run_pipeline
import sys

if __name__ == '__main__':
    inp = 'example_multi_segments.json'
    out = 'demo_multi_segment.svg'
    if len(sys.argv) > 1:
        inp = sys.argv[1]
    if len(sys.argv) > 2:
        out = sys.argv[2]
    run_pipeline(inp, out)