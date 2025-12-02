"""
Keyed list reconciliation for Evolve.

Reconciles old children vs new children using keys.
Only minimal DOM operations are executed.
Based on snabbdom O(n) algorithm.
"""

from typing import List
from ..dom.dom import Element
from ..kernel.kernel import kernel


def reconcile(parent_id: int, old: List[Element], new: List[Element]):
    """
    Reconcile two lists of Elements under the same parent container.
    Uses Element.key for matching.

    Steps:
    1. Try key-based mapping
    2. Move existing DOM nodes
    3. Insert new DOM nodes
    4. Remove old DOM nodes not present
    5. Preserve mounted child instances
    """

    # Build index: old elements by key
    old_by_key = {}
    for el in old:
        if el.key is not None:
            old_by_key[el.key] = el

    # Build final DOM order for new list
    new_dom_order = []

    for el in new:
        if el.key is not None and el.key in old_by_key:
            # re-use old element (move in DOM)
            reused = old_by_key[el.key]
            new_dom_order.append(reused)
        else:
            # brand new element → will be built
            new_dom_order.append(el)

    #  Apply DOM operations
    # We iterate new_dom_order and ensure parent contains children in this exact order.

    # 1) Ensure each element is in correct position
    for index, el in enumerate(new_dom_order):
        # Build DOM node if needed
        if el.node_id is None:
            el._build()

        # Move node to correct index in DOM
        kernel.dom.insert_at(parent_id, el.node_id, index)

    # 2) Remove elements not present anymore
    old_keys = {el.key for el in old if el.key is not None}
    new_keys = {el.key for el in new if el.key is not None}

    removed_keys = old_keys - new_keys

    for el in old:
        if el.key in removed_keys:
            # DOM remove
            if hasattr(kernel.dom, "remove"):
                kernel.dom.remove(el.node_id)
            else:
                kernel.dom.update(el.node_id, {"style": {"display": "none"}})
            el.unmount()

    return new_dom_order
