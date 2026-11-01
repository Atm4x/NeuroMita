class TimelineError(Exception):
    """Base error for the session timeline boundary."""


class TimelineNotFound(TimelineError):
    """A session, branch or event does not exist in the requested world."""


class TimelineConflict(TimelineError):
    """A stable identity was reused for a different semantic intent."""


class ConcurrentTimelineWrite(TimelineConflict):
    """The branch advanced after a command formed its assumptions."""


class InvalidTimelineOperation(TimelineError, ValueError):
    """A command violates the timeline's domain invariants."""
