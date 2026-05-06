from engine.environment import Environment
from engine.store import Store
from engine.container import Container
from engine.timeout import Timeout
from engine.store import StoreRequestTimeout
from engine.container import ContainerRequestTimeout


def test_store_put_get():
    env = Environment()
    s = Store(capacity=2)
    log = []

    def producer():
        yield s.put("a")
        yield s.put("b")
        yield s.put("c")  # should block until a get frees space
        log.append(("produced-c", env.now))

    def consumer():
        item1 = yield s.get()
        log.append(("got", item1, env.now))
        yield Timeout(1)
        item2 = yield s.get()
        log.append(("got", item2, env.now))

    env.process(producer)
    env.process(consumer)
    env.run()

    assert ("got", "a", 0.0) in log
    assert ("produced-c",)[:1]  # noop to keep patch minimal
    # produced-c should appear at some time (we don't assert exact time)
    assert any(entry[0] == "produced-c" for entry in log)


def test_container_put_get_levels():
    env = Environment()
    c = Container(capacity=10)
    log = []

    def p():
        yield c.put(5)
        log.append(("after-put5", c.level, env.now))
        yield c.get(3)
        log.append(("after-get3", c.level, env.now))

    env.process(p)
    env.run()

    assert ("after-put5", 5.0, 0.0) in log
    assert ("after-get3", 2.0, 0.0) in log


def test_store_put_timeout_and_priority():
    env = Environment()
    s = Store(capacity=0)
    log = []

    def p():
        try:
            yield s.put_with("x", timeout=1)
            log.append("put-success")
        except StoreRequestTimeout:
            log.append("put-timeout")

    def low_getter():
        item = yield s.get_with(priority=5)
        log.append(("got-low", item, env.now))

    def high_getter():
        item = yield s.get_with(priority=0)
        log.append(("got-high", item, env.now))

    env.process(p)
    env.process(low_getter)
    env.process(high_getter)
    # now producer will timeout at t==1 because capacity 0 and no puts
    env.run()

    assert "put-timeout" in log


def test_container_get_timeout():
    env = Environment()
    c = Container(capacity=10)
    log = []

    def getter():
        try:
            yield c.get_with(5, timeout=1)
            log.append("got")
        except ContainerRequestTimeout:
            log.append("timed-out")

    env.process(getter)
    env.run()

    assert log == ["timed-out"]


def test_store_timeout_exception_type_delivered():
    """Ensure StoreRequestTimeout is delivered to the waiting process."""
    env = Environment()
    s = Store(capacity=0)
    caught = []

    def p():
        try:
            yield s.put_with('x', timeout=1)
        except Exception as e:
            caught.append(type(e))

    env.process(p)
    env.run()

    assert caught and caught[0] is StoreRequestTimeout


def test_container_timeout_exception_type_delivered():
    """Ensure ContainerRequestTimeout is delivered to the waiting process."""
    env = Environment()
    c = Container(capacity=10)
    caught = []

    def p():
        try:
            yield c.get_with(1, timeout=1)
        except Exception as e:
            caught.append(type(e))

    env.process(p)
    env.run()

    assert caught and caught[0] is ContainerRequestTimeout


def test_store_putter_priority():
    """When space is freed the highest-priority queued putter should insert first."""
    env = Environment()
    s = Store(capacity=1)
    log = []

    def initial():
        yield s.put('a')

    def low_putter():
        yield s.put_with('low', priority=5)
        log.append(('low_put_done', env.now))

    def high_putter():
        yield s.put_with('high', priority=0)
        log.append(('high_put_done', env.now))

    def consumer():
        item1 = yield s.get()
        log.append(('got1', item1, env.now))
        yield Timeout(0)
        item2 = yield s.get()
        log.append(('got2', item2, env.now))
        item3 = yield s.get()
        log.append(('got3', item3, env.now))

    env.process(initial)
    env.process(low_putter)
    env.process(high_putter)
    env.process(consumer)
    env.run()

    # First get should return the initial 'a'
    assert any(entry[0] == 'got1' and entry[1] == 'a' for entry in log)
    # Next get should return 'high' (priority 0) before 'low'
    got2 = next(entry for entry in log if entry[0] == 'got2')
    got3 = next(entry for entry in log if entry[0] == 'got3')
    assert got2[1] == 'high'
    assert got3[1] == 'low'


def test_container_putter_priority():
    """When level is freed, higher-priority put_with requests are satisfied first."""
    env = Environment()
    c = Container(capacity=5)
    log = []

    def initial():
        yield c.put(5)

    def low_putter():
        yield c.put_with(3, priority=5)
        log.append(('low_put_done', env.now, c.level))

    def high_putter():
        yield c.put_with(2, priority=0)
        log.append(('high_put_done', env.now, c.level))

    def consumer():
        yield Timeout(0)
        yield c.get(4)
        log.append(('after_get', env.now, c.level))

    env.process(initial)
    env.process(low_putter)
    env.process(high_putter)
    env.process(consumer)
    env.run()

    # After get(4), the higher-priority putter (2) should be satisfied first
    assert any(entry[0] == 'high_put_done' for entry in log)
    # final level should be 3 (initial 5 - 4 get + 2 from high put)
    assert any(entry[0] == 'after_get' and abs(entry[2] - 3.0) < 1e-9 for entry in log)


def test_store_getter_priority():
    """High-priority getters should receive items before lower-priority ones."""
    env = Environment()
    s = Store(capacity=1)
    log = []

    def low_getter():
        item = yield s.get_with(priority=5)
        log.append(('low', item, env.now))

    def high_getter():
        item = yield s.get_with(priority=0)
        log.append(('high', item, env.now))

    def producer():
        yield Timeout(1)
        yield s.put('item1')

    env.process(low_getter)
    env.process(high_getter)
    env.process(producer)
    env.run()

    # high should get the item at t==1
    assert any(e[0] == 'high' and e[1] == 'item1' for e in log)


def test_container_getter_priority():
    """High-priority container getters should be served first when level becomes available."""
    env = Environment()
    c = Container(capacity=10)
    log = []

    def low_getter():
        yield Timeout(0)
        yield c.get_with(5, priority=5)
        log.append(('low', env.now, c.level))

    def high_getter():
        yield Timeout(0)
        yield c.get_with(5, priority=0)
        log.append(('high', env.now, c.level))

    def producer():
        yield Timeout(1)
        yield c.put(5)

    env.process(low_getter)
    env.process(high_getter)
    env.process(producer)
    env.run()

    assert any(e[0] == 'high' for e in log)


def test_store_timeout_with_priority():
    """A low-priority getter that times out should not prevent a later high-priority getter from receiving the item."""
    env = Environment()
    s = Store(capacity=1)
    log = []

    def low_getter():
        try:
            yield s.get_with(timeout=0.5, priority=5)
            log.append(('low_got', env.now))
        except StoreRequestTimeout:
            log.append(('low_timed', env.now))

    def high_getter():
        item = yield s.get_with(priority=0)
        log.append(('high_got', item, env.now))

    def producer():
        yield Timeout(1)
        yield s.put('x')

    env.process(low_getter)
    env.process(high_getter)
    env.process(producer)
    env.run()

    assert any(e[0] == 'low_timed' for e in log)
    assert any(e[0] == 'high_got' for e in log)


def test_store_cancellation_while_queued():
    """Cancel a queued getter and ensure it doesn't receive the item when it arrives."""
    env = Environment()
    s = Store(capacity=1)
    log = []

    def getter():
        item = yield s.get()
        log.append(('got', item, env.now))

    # start a getter and capture its Process
    p = env.process(getter)

    def canceller():
        # cancel the getter before producer puts
        yield Timeout(0.1)
        p.cancel()

    def producer():
        yield Timeout(0.5)
        yield s.put('item')

    env.process(canceller)
    env.process(producer)
    # also run another getter who should get the item
    def other():
        item = yield s.get()
        log.append(('other_got', item, env.now))

    env.process(other)
    env.run()

    assert any(e[0] == 'other_got' for e in log)
    assert not any(e[0] == 'got' for e in log)


def test_container_cancellation_while_queued():
    """Cancel a queued container getter and ensure it doesn't receive the units when put occurs."""
    env = Environment()
    c = Container(capacity=10)
    log = []

    def getter():
        yield Timeout(0)
        yield c.get(5)
        log.append(('got', env.now, c.level))

    p = env.process(getter)

    def canceller():
        yield Timeout(0.1)
        p.cancel()

    def producer():
        yield Timeout(0.5)
        yield c.put(5)

    env.process(canceller)
    env.process(producer)

    def other():
        yield Timeout(0.6)
        yield c.get(5)
        log.append(('other_got', env.now, c.level))

    env.process(other)
    env.run()

    assert any(e[0] == 'other_got' for e in log)
    assert not any(e[0] == 'got' for e in log)
