import threading
from typing import Callable, TypeVar

T = TypeVar('T')


def shared(factory: Callable[[], T]) -> Callable[[], T]:
    '''
    one instance per process, built on first use. Sync workers start at the same moment,
    so creation is locked: an API's limits only hold if every worker shares one client
    '''
    lock = threading.Lock()
    instance = None

    def get() -> T:
        nonlocal instance
        with lock:
            if instance is None:
                instance = factory()
            return instance

    get.created = lambda: instance is not None
    return get
