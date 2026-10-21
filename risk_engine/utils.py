"""Small helpers used across risk-engine: timing and retrying."""

import functools
import time


def timed(func):
    """Decorator: print how long each call to `func` takes."""

    @functools.wraps(func)  # keep func's real name and docstring on the wrapper
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} took {elapsed:.3f}s")
        return result

    return wrapper


class Timer:
    """Context manager: time a block of code.

    with Timer("load prices"):
        ...
    """

    def __init__(self, label="block"):
        self.label = label
        self.elapsed = None

    def __enter__(self):
        self.start = time.perf_counter()
        return self  # lets you write `with Timer() as t:` and read t.elapsed later

    def __exit__(self, exc_type, exc_value, traceback):
        self.elapsed = time.perf_counter() - self.start
        print(f"{self.label} took {self.elapsed:.3f}s")
        return False  # don't swallow exceptions raised inside the block


def retry(times=3, delay=1.0, exceptions=(Exception,)):
    """Decorator factory: retry `func` up to `times` attempts if it raises.

    @retry(times=3, delay=2.0)
    def fetch(...): ...
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == times:
                        raise  # out of attempts: let the caller see the error
                    print(f"{func.__name__} failed ({exc!r}); retry {attempt}/{times - 1} in {delay}s")
                    time.sleep(delay)

        return wrapper

    return decorator


if __name__ == "__main__":


    # Example 1: Timing a function
    @timed
    def slow_sum(n):
        """Add up 0..n-1."""
        return sum(range(n))

    print(slow_sum(10_000_000))     #prints the sum
    print(slow_sum.__name__)        # Prints the name of the function
    print(slow_sum.__doc__)         # Prints the doc string of the function


    # Example 2: Timing a block of code
    with Timer("list of squares") as f:
        squares = [i * i for i in range(2_000_000)]
    print(f"elapsed stored on the timer: {f.elapsed:.3f}s")

    calls = {"n": 0}


    # Example 3: Using the retry function
    @retry(times=3, delay=0.1)
    def flaky():
        """Fail twice, then succeed."""
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("server busy")
        return "ok"

    print(flaky())