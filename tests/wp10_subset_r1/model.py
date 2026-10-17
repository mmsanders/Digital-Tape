"""512-byte, any-subset persistence model. No Product code or operation oracle."""
from dataclasses import dataclass
from itertools import product

BLOCK = 512
EXHAUSTIVE_LIMIT = 8


def blocks(image):
    out = dict(image)
    if any(type(k) is not int or k < 0 or type(v) is not bytes or len(v) != BLOCK
           for k, v in out.items()):
        raise ValueError("expected nonnegative LBA -> 512 immutable bytes")
    return out


@dataclass(frozen=True)
class Event:
    id: int
    call: int
    lba: int
    data: bytes
    acknowledged: bool


class Device:
    """Sparse partition-view device. Absent blocks read as zero.

    Error writes are eligible for persistence even when not visible in RAM.
    An error's subsequent working-image effects must be explicitly supplied;
    otherwise reads/writes/successful barriers require resolve_working().
    A crash or failed barrier can always follow an unresolved error.
    """
    def __init__(self, initial):
        self.durable = blocks(initial)
        self.working = dict(self.durable)
        self.events = []
        self.next_id = 0
        self.calls = 0
        self.known_working = True
        self.flush_results = []

    def read(self, lba, count=1):
        if not self.known_working:
            raise ValueError("resolve error effects before subsequent I/O")
        if type(lba) is not int or lba < 0 or type(count) is not int or count < 1:
            raise ValueError("invalid block range")
        return b"".join(self.working.get(i, bytes(BLOCK)) for i in range(lba, lba + count))

    def write(self, lba, data, *, acknowledged=True, visible=None):
        if not self.known_working:
            raise ValueError("resolve error effects before subsequent I/O")
        if type(lba) is not int or lba < 0 or type(data) is not bytes or not data or len(data) % BLOCK:
            raise ValueError("atomic model requires complete 512-byte units")
        if type(acknowledged) is not bool:
            raise ValueError("acknowledged must be bool")
        n = len(data) // BLOCK
        indices = set(range(n)) if acknowledged else (set() if visible is None else set(visible))
        if any(type(i) is not int or i < 0 or i >= n for i in indices):
            raise ValueError("invalid visible block index")
        if acknowledged and visible is not None:
            raise ValueError("successful write makes every unit visible")
        for offset in range(n):
            payload = data[offset * BLOCK:(offset + 1) * BLOCK]
            self.events.append(Event(self.next_id, self.calls, lba + offset, payload, acknowledged))
            self.next_id += 1
            if offset in indices:
                self.working[lba + offset] = payload
        self.calls += 1
        if not acknowledged and visible is None:
            self.known_working = False

    def resolve_working(self, image):
        """Binding supplies observed actual working image after an error, not a durability claim."""
        self.working = blocks(image)
        self.known_working = True

    def flush(self, *, successful):
        if type(successful) is not bool:
            raise ValueError("successful must be bool")
        if successful and not self.known_working:
            raise ValueError("successful flush needs actual final working state")
        self.flush_results.append(successful)
        if successful:
            self.durable = dict(self.working)
            self.events.clear()
        # Failure does not establish a barrier. All attempted events remain eligible.

    def crash_image(self, landing_order):
        """Selected event IDs, in persistence order; no duplicated or foreign IDs."""
        ids = list(landing_order)
        by_id = {event.id: event for event in self.events}
        if any(type(i) is not int for i in ids) or len(ids) != len(set(ids)) or any(i not in by_id for i in ids):
            raise ValueError("invalid landing order")
        image = dict(self.durable)
        for i in ids:
            event = by_id[i]
            image[event.lba] = event.data
        return image

    def remount(self, landing_order):
        # A fresh object deliberately carries no volatile buffers or event log.
        return Device(self.crash_image(landing_order))


def exhaustive(events):
    """Every mask and per-LBA last-selected-version class, not every permutation.

    Cross-LBA permutations commute. For each mask, choose every possible winner
    independently at each touched LBA; all other selected events precede winners.
    This covers exactly the final images of all subset permutations.
    """
    events = list(events)
    if len(events) > EXHAUSTIVE_LIMIT:
        raise ValueError("large epoch: use recorded sampling, not exhaustive")
    for mask in range(1 << len(events)):
        selected = [e for i, e in enumerate(events) if mask & (1 << i)]
        groups = {}
        for event in selected:
            groups.setdefault(event.lba, []).append(event.id)
        for winners in product(*groups.values()):
            win = set(winners)
            order = [e.id for e in selected if e.id not in win] + list(winners)
            yield {"mask": format(mask, f"0{len(events)}b"), "landing_order": order}


def sampled(events, seed, draws=64):
    """Portable xorshift64; actual masks/orders, not seeds alone, are the replay input."""
    events = list(events)
    if type(seed) is not int or not 0 < seed < (1 << 64) or type(draws) is not int or draws < 0:
        raise ValueError("invalid sampling bounds")
    state = seed

    def rand():
        nonlocal state
        state ^= (state << 13) & ((1 << 64) - 1)
        state ^= state >> 7
        state ^= (state << 17) & ((1 << 64) - 1)
        return state

    mandatory = [[], [e.id for e in events], [events[-1].id] if events else []]
    for index in range(draws + len(mandatory)):
        order = mandatory[index][:] if index < len(mandatory) else [e.id for e in events if rand() & 1]
        if index >= len(mandatory):
            for i in range(len(order) - 1, 0, -1):
                j = rand() % (i + 1)
                order[i], order[j] = order[j], order[i]
        selected = set(order)
        mask = sum(1 << i for i, e in enumerate(events) if e.id in selected)
        yield {"seed": seed, "draw": index, "mask": format(mask, f"0{len(events)}b"), "landing_order": order}
