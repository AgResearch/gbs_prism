import collections


def consume(iterator):
    """Consume an iterator entirely, discarding values.  Purely for side-effects."""
    # from https://docs.python.org/3/library/itertools.html#itertools-recipes
    _ = collections.deque(iterator, maxlen=0)
