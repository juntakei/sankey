#!/usr/bin/env python3
"""
Sankey Diagram Generator

This script creates Sankey diagrams from input data in multiple formats:
1. JSON format (recommended) - see example_input.json
2. Text format - see example_input.txt
3. Command-line arguments

Usage:
    python sankey_diagram.py                    # Uses example_input.json
    python sankey_diagram.py -i input.json      # Use JSON file
    python sankey_diagram.py -i input.txt       # Use text file
    python sankey_diagram.py -i input.json -o output.html  # Specify output
"""

import plotly.graph_objects as go
import json
import re
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def parse_text_format(input_text: str) -> Tuple[Dict[str, float], Dict[str, List[Tuple[str, float]]]]:
    """
    Parse input data in the text format:
    Left
    A=10
    B=20
    C=30
    
    Right
    M= 5 from A, 5 from B
    N= 5 from A, 10 from B, 20 from C
    L= 5 from B, 10 from C
    
    Args:
        input_text: Input string with Left and Right sections
        
    Returns:
        Tuple of (left_nodes dict, right_nodes dict with flows)
    """
    left_nodes = {}
    right_nodes = {}
    
    lines = input_text.strip().split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check for section headers
        if line.lower() == 'left':
            current_section = 'left'
            continue
        elif line.lower() == 'right':
            current_section = 'right'
            continue
        
        if current_section == 'left':
            # Parse format: A=10
            match = re.match(r'(\w+)\s*=\s*(\d+(?:\.\d+)?)', line)
            if match:
                node_name, value = match.groups()
                left_nodes[node_name] = float(value)
        
        elif current_section == 'right':
            # Parse format: M= 5 from A, 5 from B
            match = re.match(r'(\w+)\s*=\s*(.+)', line)
            if match:
                node_name, flows_str = match.groups()
                flows = []
                
                # Parse flows: "5 from A, 5 from B"
                flow_pattern = r'(\d+(?:\.\d+)?)\s+from\s+(\w+)'
                for flow_match in re.finditer(flow_pattern, flows_str):
                    value, source = flow_match.groups()
                    flows.append((source, float(value)))
                
                if flows:
                    right_nodes[node_name] = flows
    
    return left_nodes, right_nodes


def parse_json_format(data: dict) -> Tuple[Dict[str, float], Dict[str, List[Tuple[str, float]]]]:
    """
    Parse input data in JSON format.
    
    Expected JSON structure:
    {
        "left": {
            "A": 10,
            "B": 20,
            "C": 30
        },
        "right": {
            "M": [
                {"from": "A", "value": 5},
                {"from": "B", "value": 5}
            ],
            "N": [
                {"from": "A", "value": 5},
                {"from": "B", "value": 10},
                {"from": "C", "value": 20}
            ]
        }
    }
    
    Or alternative format with arrays:
    {
        "left": [
            {"name": "A", "value": 10},
            {"name": "B", "value": 20}
        ],
        "right": {
            "M": [
                {"from": "A", "value": 5},
                {"from": "B", "value": 5}
            ]
        }
    }
    
    Args:
        data: Dictionary parsed from JSON
        
    Returns:
        Tuple of (left_nodes dict, right_nodes dict with flows)
    """
    left_nodes = {}
    right_nodes = {}
    
    # Parse left nodes
    if "left" in data:
        left_data = data["left"]
        if isinstance(left_data, dict):
            # Format: {"A": 10, "B": 20}
            left_nodes = {k: float(v) for k, v in left_data.items()}
        elif isinstance(left_data, list):
            # Format: [{"name": "A", "value": 10}, ...]
            left_nodes = {item["name"]: float(item["value"]) for item in left_data}
    
    # Parse right nodes
    if "right" in data:
        right_data = data["right"]
        for right_node, flows in right_data.items():
            flow_list = []
            for flow in flows:
                if isinstance(flow, dict):
                    source = flow.get("from") or flow.get("source")
                    value = flow.get("value") or flow.get("amount")
                    if source and value is not None:
                        flow_list.append((source, float(value)))
            if flow_list:
                right_nodes[right_node] = flow_list
    
    return left_nodes, right_nodes


def load_input_data(input_path: str) -> Tuple[Dict[str, float], Dict[str, List[Tuple[str, float]]], Optional[dict]]:
    """
    Load input data from file, auto-detecting format.
    
    Args:
        input_path: Path to input file
        
    Returns:
        Tuple of (left_nodes, right_nodes, metadata)
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    metadata = {}
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Try JSON first
    if path.suffix.lower() == '.json' or content.strip().startswith('{'):
        try:
            data = json.loads(content)
            # Extract metadata if present
            metadata = {
                "title": data.get("title", "Sankey Diagram"),
                "height": data.get("height", 600),
                "font_size": data.get("font_size", 12)
            }
            left_nodes, right_nodes = parse_json_format(data)
            return left_nodes, right_nodes, metadata
        except json.JSONDecodeError as e:
            if path.suffix.lower() == '.json':
                raise ValueError(f"Invalid JSON format: {e}")
            # If not .json extension, fall through to text format
    
    # Try text format
    left_nodes, right_nodes = parse_text_format(content)
    return left_nodes, right_nodes, metadata


def validate_flows(left_nodes: Dict[str, float], 
                   right_nodes: Dict[str, List[Tuple[str, float]]],
                   verbose: bool = True) -> bool:
    """
    Validate that flows match left node values.
    
    Returns:
        True if valid, False otherwise
    """
    left_totals = {node: 0 for node in left_nodes.keys()}
    
    for right_node, flows in right_nodes.items():
        for left_node, value in flows:
            if left_node not in left_totals:
                if verbose:
                    print(f"Warning: Flow references unknown left node '{left_node}'")
                return False
            left_totals[left_node] += value
    
    is_valid = True
    for node, total in left_totals.items():
        expected = left_nodes[node]
        if abs(total - expected) > 0.01:
            if verbose:
                print(f"Warning: {node} has total flow {total} but expected {expected}")
            is_valid = False
        elif verbose:
            print(f"✓ {node}: {total} (expected {expected})")
    
    return is_valid


def create_sankey_diagram(left_nodes: Dict[str, float], 
                          right_nodes: Dict[str, List[Tuple[str, float]]],
                          title: str = "Sankey Diagram",
                          height: int = 600,
                          font_size: int = 12) -> go.Figure:
    """
    Create a Sankey diagram from parsed data.
    
    Args:
        left_nodes: Dictionary of left node names to values
        right_nodes: Dictionary of right node names to list of (source, value) tuples
        title: Title for the diagram
        height: Height of the diagram in pixels
        font_size: Font size for labels
        
    Returns:
        Plotly figure object
    """
    # Handle nodes that appear in both left and right
    # If a node appears in both, we need separate indices for left and right positions
    left_labels = list(left_nodes.keys())
    right_labels = list(right_nodes.keys())
    
    # Find duplicates
    duplicates = set(left_labels) & set(right_labels)
    
    # Create unique labels for display and indexing
    # For duplicates, we'll use the same name but they'll be at different positions
    # We need separate index mappings for left and right
    all_labels = []
    left_indices = {}  # Maps left node name to its index
    right_indices = {}  # Maps right node name to its index
    
    # Add left nodes
    for i, label in enumerate(left_labels):
        all_labels.append(label)
        left_indices[label] = i
    
    # Add right nodes (they come after left nodes)
    num_left = len(left_labels)
    for i, label in enumerate(right_labels):
        idx = num_left + i
        all_labels.append(label)
        right_indices[label] = idx
    
    # Build source, target, and value lists
    source = []
    target = []
    value = []
    
    # Add flows from left to right
    for right_node, flows in right_nodes.items():
        right_idx = right_indices[right_node]
        for left_node, flow_value in flows:
            if left_node in left_indices:
                left_idx = left_indices[left_node]
                source.append(left_idx)
                target.append(right_idx)
                value.append(flow_value)
    
    # Create color palette
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
              '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    
    # Assign colors to nodes based on their position in all_labels
    # Color assignment rules:
    # 1. Each node gets a color based on its index position (0, 1, 2, ...)
    # 2. Colors cycle through the palette if there are more nodes than colors
    # 3. If a node appears in BOTH left and right groups:
    #    - The left-side instance gets a color based on its left position
    #    - The right-side instance gets a color based on its right position
    #    - They will have DIFFERENT colors (unless by coincidence)
    # Example: If "A" is 1st on left and 1st on right:
    #    - Left "A" (index 0) → colors[0] = '#1f77b4' (blue)
    #    - Right "A" (index 3, if 3 left nodes) → colors[3] = '#d62728' (red)
    node_colors = []
    for i, label in enumerate(all_labels):
        node_colors.append(colors[i % len(colors)])
    
    # Create the Sankey diagram
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=all_labels,
            color=node_colors
        ),
        link=dict(
            source=source,
            target=target,
            value=value,
            color='rgba(180, 180, 180, 0.4)'
        )
    )])
    
    fig.update_layout(
        title_text=title,
        font_size=font_size,
        height=height
    )
    
    return fig


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Generate Sankey diagrams from input data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python sankey_diagram.py                           # Use example_input.json
  python sankey_diagram.py -i data.json               # Use JSON file
  python sankey_diagram.py -i data.txt                # Use text file
  python sankey_diagram.py -i data.json -o output.html # Specify output
        """
    )
    parser.add_argument('-i', '--input', 
                       default='example_input.json',
                       help='Input file (JSON or text format, default: example_input.json)')
    parser.add_argument('-o', '--output',
                       help='Output HTML file (default: sankey_diagram.html)')
    parser.add_argument('--no-validate', 
                       action='store_true',
                       help='Skip flow validation')
    parser.add_argument('--no-show',
                       action='store_true',
                       help='Do not open diagram in browser')
    
    args = parser.parse_args()
    
    # Determine output file
    if args.output:
        output_file = args.output
    else:
        output_file = "sankey_diagram.html"
    
    # Load input data
    try:
        print(f"Loading input from {args.input}...")
        left_nodes, right_nodes, metadata = load_input_data(args.input)
        
        print(f"Left nodes: {left_nodes}")
        print(f"Right nodes: {right_nodes}")
        
        # Validate flows
        if not args.no_validate:
            print("\nValidating flows...")
            validate_flows(left_nodes, right_nodes)
        
        # Create diagram
        print("\nCreating Sankey diagram...")
        title = metadata.get("title", "Sankey Diagram")
        height = metadata.get("height", 600)
        font_size = metadata.get("font_size", 12)
        
        fig = create_sankey_diagram(left_nodes, right_nodes, title, height, font_size)
        
        # Save as HTML
        fig.write_html(output_file)
        print(f"Diagram saved to {output_file}")
        
        # Show in browser
        if not args.no_show:
            fig.show()
    
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except (ValueError, KeyError) as e:
        print(f"Error parsing input: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
