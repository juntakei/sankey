# Color Behavior in Sankey Diagrams

## How Colors Are Assigned

The script assigns colors to nodes based on their **position** in the diagram, not by name. This means:

### Normal Case (No Duplicates)

If nodes appear only on one side:
- **Left nodes**: Colors assigned in order (A=color[0], B=color[1], C=color[2], ...)
- **Right nodes**: Colors continue from where left nodes ended

**Example:**
```
Left: A, B, C
Right: M, N, L

Colors:
- A (left, index 0) → Blue (#1f77b4)
- B (left, index 1) → Orange (#ff7f0e)
- C (left, index 2) → Green (#2ca02c)
- M (right, index 3) → Red (#d62728)
- N (right, index 4) → Purple (#9467bd)
- L (right, index 5) → Brown (#8c564b)
```

### Duplicate Nodes (Appears in Both Left and Right)

**Important:** If a node name appears in **both** left and right groups, they are treated as **separate nodes** at different positions:

- **Left instance**: Gets color based on its position among left nodes
- **Right instance**: Gets color based on its position among right nodes
- **They will have DIFFERENT colors** (unless by coincidence)

**Example:**
```json
{
  "left": {"A": 10, "B": 20},
  "right": {"A": [...], "M": [...]}
}
```

Color assignment:
- **A (left, index 0)** → Blue (#1f77b4)
- **B (left, index 1)** → Orange (#ff7f0e)
- **A (right, index 2)** → Green (#2ca02c) ← Different color!
- **M (right, index 3)** → Red (#d62728)

### Color Palette

The script uses a 10-color palette that cycles if you have more than 10 nodes:
1. Blue (#1f77b4)
2. Orange (#ff7f0e)
3. Green (#2ca02c)
4. Red (#d62728)
5. Purple (#9467bd)
6. Brown (#8c564b)
7. Pink (#e377c2)
8. Gray (#7f7f7f)
9. Olive (#bcbd22)
10. Cyan (#17becf)

After 10 nodes, it cycles back to the beginning.

## Visual Example

Try running:
```bash
python sankey_diagram.py -i example_duplicate.json -o example_duplicate.html
```

This example shows node "A" appearing in both left and right groups, and you'll see they have different colors.

## Why This Design?

1. **Position-based coloring** makes it easy to visually distinguish nodes
2. **Separate colors for duplicates** helps clarify that they're separate instances
3. **Consistent ordering** makes diagrams predictable and easier to read
