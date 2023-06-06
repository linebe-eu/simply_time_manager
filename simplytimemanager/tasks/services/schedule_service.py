import logging
from datetime import time
from dataclasses import dataclass

from sortedcontainers import SortedList
from django.conf import settings
from tasks.models import TaskState, Schedule, Task
from tasks.services.common import Singleton
from tasks.services.exceptions import ConflictActiveTaskSchedulesException, \
    ConflictActiveTaskSchedulesMissingException, LogicError

logging.basicConfig(level=logging.INFO)
verbose = settings.DEBUG


@dataclass
class ScheduleConflict:
    task_name: str
    start_time: time
    end_time: time
    weekdays: tuple[str]


# TODO Consider more appropriate structures or tools for implementation
class ScheduleService(metaclass=Singleton):
    """
    This class provides methods for adding, removing current active tasks to the current
    schedule. (It appears in memory).\n
    There are two always sorted lists in memory. The first list contains the start times of the
    active tasks, together with the task with which this time is associated.
    The second list contains the end times for the execution of active tasks, together with the
    task with which this time is associated.\n
    When a task is added to the schedule, these lists are used to verify that this task does not
    have time and day of the week conflicts with other active tasks. And if so, the task is added:
    its start and end times are added to the corresponding lists.\n
    """

    def __init__(self):
        self._starts: SortedList
        self._ends: SortedList
        self._start_service()
        if verbose:
            logging.info(f"{ScheduleService.__name__} started")

    def restart_service(self):
        if verbose:
            logging.info(f"{ScheduleService.__name__} restarted")
        self._start_service()

    def add_task_schedules(self, instance: Task):
        """
        Adding task schedules to memory (marking schedules as active) if all are completed
        conditions according to business logic.
        """
        task_schedules: list[Schedule] = instance.schedules.all()

        if not task_schedules:
            raise ConflictActiveTaskSchedulesMissingException()

        conflicts: list[ScheduleConflict] = []
        for task_schedule in task_schedules:
            if conflict := self._check_conflict(task_schedule):
                conflicts.append(conflict)
        if conflicts:
            raise ConflictActiveTaskSchedulesException()
        for task_schedule in task_schedules:
            self._add_schedule(task_schedule)

        if verbose:
            logging.info(f"{ScheduleService.__name__} add task: {instance}")

    def remove_task_schedules(self, instance: Task):
        """
        Deleting task schedules from memory (marking schedules as inactive).
        """
        task_schedules: list[Schedule] = instance.schedules.all()
        if not task_schedules:
            raise LogicError()
        for task_schedule in task_schedules:
            self._remove_schedule(task_schedule)

        if verbose:
            logging.info(f"{ScheduleService.__name__} remove task: {instance}")

    def _start_service(self):
        """Initialization of lists, adding schedules of already active tasks
        from the database to them."""
        self._starts = SortedList(key=lambda x: x[0])
        self._ends = SortedList(key=lambda x: x[0])
        active_schedules = Schedule.objects.filter(task__state=TaskState.ACTIVE)

        for active_schedule in active_schedules:
            self._starts.add((active_schedule.start_time, active_schedule))
            self._ends.add((active_schedule.end_time, active_schedule))

        if verbose:
            logging.debug("{} contains:\n{}".format(ScheduleService.__name__,
                                                    "\n".join([str(schedule) for _, schedule in
                                                               self._starts])))

    def _add_schedule(self, instance: Schedule):
        """This method that adds one task schedule to the service."""
        self._starts.add((instance.start_time, instance))
        self._ends.add((instance.end_time, instance))

        if verbose:
            logging.debug("{}: added schedule:\n{}".format(ScheduleService.__name__, instance))

    def _remove_schedule(self, instance: Schedule):
        """This method that removes one task schedule per service."""
        self._starts.remove((instance.start_time, instance))
        self._ends.remove((instance.end_time, instance))

        if verbose:
            logging.debug("{} remove schedule:\n{}".format(ScheduleService.__name__, instance))

    def _check_conflict(self, instance: Schedule) -> ScheduleConflict | None:
        """This method that checks the Schedule for conflicts with active Schedules"""
        if verbose:
            logging.debug(
                "{} checked conflict schedule:\n{}".format(ScheduleService.__name__, instance))

        r_boundary_starts = self._starts.bisect_left((instance.end_time,))
        start_conflicts: set[Schedule] = set(
            [schedule for _, schedule in self._starts[:r_boundary_starts]])

        l_boundary_ends = self._ends.bisect_right((instance.start_time,))
        end_conflicts: set[Schedule] = set(
            [schedule for _, schedule in self._ends[l_boundary_ends:]])

        if time_conflicts := start_conflicts & end_conflicts:
            instance_days = set([day for day, is_ in instance.weekdays if is_])
            for time_conflict in time_conflicts:
                time_conflict_days = set([day for day, is_ in time_conflict.weekdays if is_])
                if conflict_days := instance_days & time_conflict_days:
                    schedule_conflict = ScheduleConflict(time_conflict.task.title,
                                                         time_conflict.start_time,
                                                         time_conflict.end_time,
                                                         tuple(conflict_days))
                    if verbose:
                        logging.warning(
                            "{} conflict:\n{}".format(ScheduleService.__name__, schedule_conflict))
                    return schedule_conflict
