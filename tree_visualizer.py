from typing import Dict, Any

def _render_node(name: str, node: Dict[str, Any], prefix: str, is_last: bool) -> str:
    """Recursively renders a single node and its children."""
    lines = []
    connector = "└── " if is_last else "├── "
    lines.append(f"{prefix}{connector}{name}")

    if isinstance(node, dict) and node:
        children = list(node.items())
        count = len(children)
        new_prefix = prefix + ("    " if is_last else "│   ")
        for i, (child_name, child_node) in enumerate(children):
            is_child_last = (i == count - 1)
            lines.append(_render_node(child_name, child_node, new_prefix, is_child_last))

    return "\n".join(lines)

def format_tree(tree: Dict[str, Any]) -> str:
    """
    Formats a nested dictionary into a user-friendly ASCII tree string.

    The input dictionary is expected to have a single key at its root, which
    represents the root of the tree.

    Example:
        tree_data = {
            "root": {
                "child1": {},
                "child2": {
                    "grandchild1": {}
                },
                "child3": {}
            }
        }
        print(format_tree(tree_data))

    Args:
        tree: A dictionary representing the tree. Must have a single root key.

    Returns:
        A string containing the formatted ASCII tree.
    
    Raises:
        ValueError: If the input dictionary is empty or has more than one root key.
    """
    if not tree or not isinstance(tree, dict) or len(tree) != 1:
        raise ValueError("Input must be a dictionary with a single root key.")

    root_name = list(tree.keys())[0]
    root_node = tree[root_name]

    output = [root_name]
    if isinstance(root_node, dict):
        children = list(root_node.items())
        count = len(children)
        for i, (child_name, child_node) in enumerate(children):
            is_last = (i == count - 1)
            output.append(_render_node(child_name, child_node, "", is_last))

    return "\n".join(output)
