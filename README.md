# Sankey Diagram Generator

A Python script to generate interactive Sankey diagrams from various input formats.

## Features

- **Multiple input formats**: JSON (recommended), text files
- **Command-line interface**: Easy to use with options
- **Flow validation**: Automatically validates that flows match source values
- **Interactive output**: Generates HTML files viewable in any browser

## Installation

1. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install plotly
```

## Usage

### Basic Usage

```bash
# Use default example_input.json
python sankey_diagram.py

# Specify input file
python sankey_diagram.py -i data.json

# Specify input and output files
python sankey_diagram.py -i data.json -o output.html

# Use text format
python sankey_diagram.py -i data.txt
```

### Command-line Options

- `-i, --input`: Input file (default: `example_input.json`)
- `-o, --output`: Output HTML file (default: `sankey_diagram.html`)
- `--no-validate`: Skip flow validation
- `--no-show`: Do not open diagram in browser

## Input Formats

### JSON Format (Recommended)

The JSON format is the most flexible and recommended approach:

```json
{
  "title": "My Sankey Diagram",
  "height": 600,
  "font_size": 12,
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
```

**Advantages:**
- Easy to generate programmatically
- Supports metadata (title, height, font_size)
- Easy to validate and parse
- Works well with other tools

**Alternative JSON format** (using arrays for left nodes):
```json
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
```

### Text Format

The text format is simpler but less flexible:

```
Left
A=10
B=20
C=30

Right
M= 5 from A, 5 from B
N= 5 from A, 10 from B, 20 from C
L= 5 from B, 10 from C
```

**Advantages:**
- Human-readable
- Easy to write manually
- Simple format

**Disadvantages:**
- No metadata support
- Less flexible for programmatic generation

## Examples

See `example_input.json` and `example_input.txt` for sample input files.

## Output

The script generates an interactive HTML file that can be:
- Opened in any web browser
- Embedded in web pages
- Shared with others
- Exported to images using browser tools

## Validation

By default, the script validates that:
- All flows from left nodes match the total values
- All referenced left nodes exist
- No flows reference non-existent nodes

Use `--no-validate` to skip validation.
