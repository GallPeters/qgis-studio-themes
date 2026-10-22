"""One event filter per watched object, shared by the plugin's parts.

The icon swapper and the toolbar names both watch the main window and
every toolbar. Each installed event filter costs a call from Qt into
Python for every event the object receives (paints, layout requests, each
action enabled or disabled on a selection change...). Through the hub an
object costs one such call per event, however many parts watch it, and
event types no part asked for return at once, before any part's code
runs.
"""
from qgis.PyQt import sip
from qgis.PyQt.QtCore import QObject


class EventHub(QObject):
    """Calls each part's handler(watched, event) for the event types it
    watches an object for (see watch)."""

    # Entries of deleted objects are dropped once the table doubles.
    PRUNE_MIN = 200

    def __init__(self):
        super().__init__()
        # id(object) -> (object, {part: (types, handler)}, all types). The
        # object is kept referenced, so its id is never reused meanwhile.
        self._watched = {}
        self._prune_at = self.PRUNE_MIN

    def watch(self, obj, part, types, handler):
        """Call handler(obj, event) for events of `types` (QEvent.Type
        values) on `obj`, for `part` (any hashable owner, see unwatch).
        Watching again adds types (one handler per part and object)."""
        if len(self._watched) >= self._prune_at:
            self._prune()
        entry = self._watched.get(id(obj))
        if entry is None:
            entry = (obj, {}, set())
            self._watched[id(obj)] = entry
            obj.installEventFilter(self)
        known = entry[1].get(part, (frozenset(), None))[0]
        entry[1][part] = (known | frozenset(types), handler)
        entry[2].update(types)

    def unwatch(self, obj, part):
        """Stop calling `part` for `obj`; the filter goes once no part
        watches it."""
        entry = self._watched.get(id(obj))
        if entry is None or entry[1].pop(part, None) is None:
            return
        if entry[1]:
            entry[2].clear()
            for types, _handler in entry[1].values():
                entry[2].update(types)
            return
        del self._watched[id(obj)]
        if not sip.isdeleted(obj):
            obj.removeEventFilter(self)

    def watches(self, obj, part):
        entry = self._watched.get(id(obj))
        return entry is not None and part in entry[1]

    def _prune(self):
        self._watched = {key: entry for key, entry in self._watched.items() if not sip.isdeleted(entry[0])}
        self._prune_at = max(self.PRUNE_MIN, 2 * len(self._watched))

    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        entry = self._watched.get(id(watched))
        if entry is None:
            return False
        kind = event.type()
        if kind not in entry[2]:
            return False
        for types, handler in list(entry[1].values()):
            if kind in types:
                handler(watched, event)
        return False
