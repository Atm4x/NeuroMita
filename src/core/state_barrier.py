from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from threading import Condition, get_ident
from time import monotonic


_bound_state = ContextVar("session_state_owner", default=None)


class StateUnavailable(RuntimeError):
    """State belongs to an obsolete operation or an unfinished transition."""


class StateBarrier:
    """Drain short state operations without holding locks during provider calls."""

    def __init__(self):
        self._condition = Condition()
        self._epoch = 0
        self._active = 0
        self._owner = None
        self._poison = ""
        self._ticket = ContextVar(f"state_ticket:{id(self)}", default=None)
        self._depth = ContextVar(f"state_depth:{id(self)}", default=None)

    def _execution_depth(self):
        try:
            task = asyncio.current_task()
        except RuntimeError:
            task = None
        identity = (get_ident(), task)
        inherited = self._depth.get()
        return identity, inherited[1] if inherited is not None and inherited[0] == identity else 0

    def ticket(self) -> int:
        with self._condition:
            return self._epoch if self.exclusive_owner or self._ticket.get() is None else self._ticket.get()

    def is_current(self, ticket: int) -> bool:
        with self._condition:
            return ticket == self._epoch and not self._poison

    def current_ticket(self) -> int:
        with self._condition:
            return self._epoch

    @property
    def exclusive_owner(self) -> bool:
        with self._condition:
            return self._owner == get_ident()

    @property
    def poisoned(self) -> bool:
        with self._condition:
            return bool(self._poison)

    @contextmanager
    def bind(self, ticket: int):
        token = self._ticket.set(ticket)
        owner = _bound_state.set((self, ticket))
        try:
            yield
        finally:
            self._ticket.reset(token)
            _bound_state.reset(owner)

    @contextmanager
    def access(self, *, wait: bool = False, timeout: float = 30):
        with self._condition:
            binding = _bound_state.get()
            if binding is not None and binding[0] is not self:
                raise StateUnavailable("This operation belongs to an earlier application runtime")
            identity, current_depth = self._execution_depth()
            nested = current_depth > 0
            owner = self._owner == get_ident()
            if self._poison and not owner:
                raise StateUnavailable(self._poison)
            deadline = monotonic() + timeout
            while not nested and self._owner is not None and not owner:
                remaining = deadline - monotonic()
                if not wait or remaining <= 0:
                    raise StateUnavailable("Session state is being restored or captured")
                self._condition.wait(remaining)
            if self._poison and not owner:
                raise StateUnavailable(self._poison)
            ticket = self._ticket.get()
            if not owner and ticket is not None and ticket != self._epoch:
                raise StateUnavailable("This operation belongs to an earlier session state")
            if not nested:
                self._active += 1
            depth = self._depth.set((identity, current_depth + 1))
        try:
            yield
        finally:
            self._depth.reset(depth)
            if not nested:
                with self._condition:
                    self._active -= 1
                    self._condition.notify_all()

    @contextmanager
    def exclusive(self, *, invalidate: bool = False, timeout: float = 30):
        deadline = monotonic() + timeout
        with self._condition:
            binding = _bound_state.get()
            if binding is not None and (binding[0] is not self or binding[1] != self._epoch):
                raise StateUnavailable("An obsolete operation cannot initiate a state transition")
            if self._owner is not None or self._execution_depth()[1]:
                raise StateUnavailable("A state transition cannot nest inside another state operation")
            self._owner = get_ident()
            try:
                while self._active:
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        raise StateUnavailable("State operations did not finish before the transition timeout")
                    self._condition.wait(remaining)
                if invalidate:
                    self._epoch += 1
            except BaseException:
                self._owner = None
                self._condition.notify_all()
                raise
        try:
            yield
        finally:
            with self._condition:
                self._owner = None
                self._condition.notify_all()

    def poison(self, reason: str):
        with self._condition:
            self._poison = reason

    def invalidate(self):
        with self._condition:
            if self._owner != get_ident() or self._active:
                raise StateUnavailable("Invalidation requires exclusive ownership after draining state operations")
            self._epoch += 1

    def recovered(self):
        with self._condition:
            if self._owner != get_ident():
                raise StateUnavailable("Recovery requires an exclusive state transition")
            self._poison = ""


def current_state_barrier() -> StateBarrier | None:
    from core.services import services
    return services().get_optional(StateBarrier)


@contextmanager
def state_access(*, wait: bool = False):
    barrier = current_state_barrier()
    binding = _bound_state.get()
    if binding is not None and binding[0] is not barrier:
        raise StateUnavailable("The operation's application runtime is no longer active")
    if barrier is None:
        yield
    else:
        with barrier.access(wait=wait):
            yield


def state_operation(function=None, *, wait: bool = False):
    if function is None:
        return lambda target: state_operation(target, wait=wait)
    @wraps(function)
    def guarded(*args, **kwargs):
        with state_access(wait=wait):
            return function(*args, **kwargs)
    return guarded


@contextmanager
def external_state_operation(owner=None):
    """Start one new input operation from a long-lived service, preserving its runtime owner."""
    barrier = current_state_barrier()
    if owner is not None and owner is not barrier:
        raise StateUnavailable("This input service belongs to an earlier application runtime")
    if barrier is None:
        token = _bound_state.set(None)
        try:
            yield
        finally:
            _bound_state.reset(token)
    else:
        with barrier.bind(barrier.current_ticket()):
            yield


def bind_state_job(function):
    barrier = current_state_barrier()
    binding = _bound_state.get()
    if binding is not None and (barrier is None or not barrier.exclusive_owner):
        barrier, ticket = binding
    else:
        ticket = barrier.ticket() if barrier is not None else None
    if barrier is None:
        return function

    @wraps(function)
    def bound(*args, **kwargs):
        with barrier.bind(ticket):
            return function(*args, **kwargs)
    return bound


def state_job(function=None, *, check_result=False):
    """Pin queued work at admission; optionally reject obsolete computed results."""
    if function is None:
        return lambda target: state_job(target, check_result=check_result)
    @wraps(function)
    def admitted(*args, **kwargs):
        def run():
            with state_access(wait=True):
                pass
            result = function(*args, **kwargs)
            if check_result:
                with state_access(wait=True):
                    pass
            return result
        return bind_state_job(run)()
    return admitted


class StateLease:
    """Detached provenance that survives async queues and transport task snapshots."""

    __slots__ = ("_barrier", "_ticket")

    def __init__(self, barrier: StateBarrier, ticket: int):
        self._barrier, self._ticket = barrier, ticket

    @classmethod
    def capture(cls):
        barrier = current_state_barrier()
        return cls(barrier, barrier.ticket()) if barrier is not None else None

    @property
    def current(self) -> bool:
        return current_state_barrier() is self._barrier and self._barrier.is_current(self._ticket)

    def require_current(self):
        if not self.current:
            raise StateUnavailable("The operation belongs to a previous session state")

    def __deepcopy__(self, _memo):
        return self
