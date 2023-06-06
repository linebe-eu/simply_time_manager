from rest_framework.exceptions import APIException
from rest_framework import status
from tasks.models import TaskState


class BaseServiceException(APIException):
    pass


class LogicError(BaseServiceException):
    """If this exception is thrown at all, then there is a clear problem
    (shouldn't be like this)"""
    pass


class ConflictException(BaseServiceException):
    status_code = status.HTTP_409_CONFLICT

    default_detail = "Request conflict with the current state of the target resource"
    default_code = "conflict"


class ConflictTaskStateException(ConflictException):
    default_detail = "Transiting the current state of the task is not possible, " \
                     "to the state you specified"
    possible_state_changing = {TaskState.PLANNED: (TaskState.ACTIVE,),
                               TaskState.ACTIVE: (TaskState.PAUSED, TaskState.FINISHED),
                               TaskState.PAUSED: (TaskState.ACTIVE, TaskState.FINISHED),
                               TaskState.FINISHED: (TaskState.ARCHIVED,),
                               TaskState.ARCHIVED: (TaskState.FINISHED,)
                               }
    default_code = "conflict task state"

    def __init__(self, current_state):
        detail = self.default_detail
        if possible_states := self.possible_state_changing.get(current_state):
            many_suffix = "s" if len(possible_states) > 1 else ""
            many_be = "are" if len(possible_states) > 1 else "is"
            possible_states_str = "'" + "' and '".join(possible_states) + "'"
            detail += f". From state '{current_state}', only transition{many_suffix} to " \
                      f"state{many_suffix} {possible_states_str} {many_be} possible."

        super().__init__(detail=detail)


class ConflictTaskStateAtCreationException(ConflictException):
    default_detail = f"State of the task at her creation should only be {TaskState.get_state_at_creation()}"
    default_code = "conflict task state at creation"


class ConflictActiveTaskSchedulesMissingException(ConflictException):
    default_detail = f"To change the state in {TaskState.ACTIVE}, " \
                     f"the task must have at least one schedule."
    default_code = "conflict active task schedules missing"


class ConflictActiveTaskSchedulesException(ConflictException):
    default_detail = f"This task's schedules conflict with the schedules of other tasks. To resolve " \
                     f"this issue, either change the schedules of the current task, or schedules of " \
                     f"other tasks, or move other tasks to state {TaskState.PAUSED}."
    default_code = "conflict active task schedules"


class ConflictDeletedTaskException(ConflictException):
    default_detail = f"Task can only be deleted from states {TaskState.PLANNED} or " \
                     f"{TaskState.FINISHED} or {TaskState.ARCHIVED}"
    default_code = "conflict deleted task"
