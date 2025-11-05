from typing import Any, Dict, MutableMapping

__all__ = ["flatten_dict"]

def flatten_dict(
    nested_dict: MutableMapping[str, Any],
    parent_key: str = "",
    sep: str = "."
) -> Dict[str, Any]:
    """
    Flattens a nested dictionary into a single-level dictionary.

    Args:
        nested_dict: The dictionary to flatten.
        parent_key: The base key to use for constructing flattened keys
                    (used internally for recursion).
        sep: The separator to use between keys.

    Returns:
        A new dictionary with a single level of keys.

    Example:
        >>> config = {
        ...     'server': {
        ...         'host': '127.0.0.1',
        ...         'port': 8080
        ...     },
        ...     'active': True
        ... }
        >>> flatten_dict(config)
        {'server.host': '127.0.0.1', 'server.port': 8080, 'active': True}
        >>> flatten_dict(config, sep='_')
        {'server_host': '127.0.0.1', 'server_port': 8080, 'active': True}
    """
    items: list[tuple[str, Any]] = []
    for k, v in nested_dict.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, MutableMapping) and v:
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)
