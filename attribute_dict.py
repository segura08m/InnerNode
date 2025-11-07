from typing import Any, Dict

class AttributeDict(dict):
    """
    A dictionary subclass that allows accessing keys as attributes.

    This class provides a more convenient way to work with nested dictionaries,
    such as configuration data, by allowing dot-notation access (e.g., `config.db.host`)
    in addition to the standard bracket notation (e.g., `config['db']['host']`).

    Nested dictionaries are recursively converted to AttributeDict instances upon access.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for key, value in self.items():
            if isinstance(value, dict):
                self[key] = AttributeDict(value)

    def __getattr__(self, name: str) -> Any:
        """Allows getting dictionary keys as attributes."""
        try:
            value = self[name]
            if isinstance(value, dict):
                # Memoize the converted dict to avoid re-creating it
                if not isinstance(value, AttributeDict):
                    value = AttributeDict(value)
                    self[name] = value
                return value
            return value
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        """Allows setting dictionary keys as attributes."""
        if isinstance(value, dict):
            value = AttributeDict(value)
        self[name] = value

    def __delattr__(self, name: str) -> None:
        """Allows deleting dictionary keys as attributes."""
        try:
            del self[name]
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AttributeDict":
        """
        Recursively converts a standard dictionary to an AttributeDict.

        Args:
            data: The dictionary to convert.

        Returns:
            A new AttributeDict instance.
        """
        if not isinstance(data, dict):
            raise TypeError("Input must be a dictionary.")
        return AttributeDict(data)
