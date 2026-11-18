### `dunzo.scheduler` (contract v1; owner: agent `b`). Pure: no I/O, no database or web imports.
```python
AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4
@dataclass(frozen=True) class SchedulerConfig:
    again_delay: timedelta = timedelta(minutes=10); day_rollover: time = time(4, 0); tz: tzinfo = timezone.utc
@dataclass(frozen=True) class ScheduleResult: state: dict[str, Any]; due: datetime   # state JSON-serializable; due aware UTC
class Scheduler(Protocol):
    name: str
    def schedule(self, state: dict | None, grade: int, now: datetime, config: SchedulerConfig) -> ScheduleResult
        # state None = the card's first review. SchedulerError if grade not in 1..4 or `now` is naive.
DEFAULT_SCHEDULER = "sm2"
def get_scheduler(name: str) -> Scheduler            # SchedulerError if unknown
class SchedulerError(ValueError): ...
def study_day(now: datetime, rollover: time, tz: tzinfo) -> date
    # the calendar date in `tz` of (now - rollover as a duration): 03:59 with rollover 04:00 belongs to the previous day
def study_day_start(day: date, rollover: time, tz: tzinfo) -> datetime   # aware UTC instant at which `day` begins
```
Guarantees: deterministic; the returned state is opaque to everyone but the scheduler that produced it; a grade of AGAIN yields `due = now + again_delay`.
