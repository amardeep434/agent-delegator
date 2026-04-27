from datetime import datetime
from typing import Any, Callable, TypeVar

T = TypeVar("T")

def sort_by_date(
    items: list[T],
    *,
    key: Callable[[T], Any] | None = None,
    date_attr: str = "date",
    reverse: bool = False,
    parse: Callable[[Any], datetime] | None = None,
) -> list[T]:
    """Sort a list of objects by date.

    Args:
        items: List of objects to sort.
        key: Optional custom key function. Receives each item, should return a date value.
        date_attr: Attribute name to extract the date from each object. Ignored if key is given.
        reverse: If True, sort in descending order.
        parse: Optional function to convert date_attr values into datetime objects
               (e.g. datetime.fromisoformat for ISO 8601 strings).

    Returns:
        A new sorted list (the original is not modified).
    """
    if key is not None:
        extract = key
    elif parse is not None:

        def extract(item: T) -> datetime:
            return parse(getattr(item, date_attr))
    else:

        def extract(item: T) -> Any:
            return getattr(item, date_attr)

    return sorted(items, key=extract, reverse=reverse)
