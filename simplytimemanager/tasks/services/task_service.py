import logging

from django.conf import settings
from .common import Singleton
from .exceptions import *
from tasks.models import TaskState, Task, Schedule
from ..serializers import TaskSerializer
from .schedule_service import ScheduleService

logging.basicConfig(level=logging.INFO)
verbose = settings.DEBUG


class TaskService(metaclass=Singleton):
    """
    Данный класс предоставляет методы для контроля состояний задач, согласно бизнес-правилам данного
    приложения.\n
    Правила смены состояний задачи:\n
        - из PLANNED можно перейти только в ACTIVE. Также задача находящееся в данном состоянии
          может быть удалена;
        - из ACTIVE можно перейти только в PAUSE или FINISHED;
        - из PAUSE можно перейти только в ACTIVE или FINISHED;
        - из FINISHED можно только в ARCHIVED. Также задача находящееся в данном состоянии может
          быть удалена;
        - из ARCHIVED можно только в FINISHED. Также задача находящееся в данном состоянии может
          быть удалена;
        - если в запросе указано состояние в которое Task не может перейти согласно данным
          правилам или задача не может быть удалена, то сообщить об этом клиенту,
          с указанием проблемы и путей её решения.
    Условия для перехода в конкретное состояние и действия во время перехода:
        - в PLANNED - (переход выполняется во время создания Task)
        - в ACTIVE - переход возможет только если [Для текущей Task должны быть созданы Schedules,
          которые не конфликтуют с Schedules других Tasks (проверка выполняется с помощью
          вспомогательного хранилища в памяти или кэша)]. Если данное условие не выполняется, то
          сообщить об этом клиенту, с указанием проблемы и путей её решения. Иначе добавить в память
          или кэш Schedules данной Task.
        - в PAUSED - удаляются связанные с Task Schedules из памяти или кэша.
        - в FINISHED - удаляются связанные с Task Schedules из БД и памяти или кэша, в случае если
          переход был выполнен из состояния ACTIVE. Если переход выполнялся из PAUSED, то удаляются
          связанные с Task Schedules из БД.
        - в ARCHIVED - нет никаких доп действий.
        - при удалении Task, удаляются связанные с Task Schedules, Notes, Reports из БД, в случае
          если удаление происходит из состояний FINISHED или ARCHIVED. Удаляются связанные с Task
          Schedules если удаление происходит из состояния PLANNED.
    """

    def __init__(self):
        self.schedules_service = ScheduleService()
        if verbose:
            logging.info(f"{TaskService.__name__} started")

    def create_task(self, serializer: TaskSerializer):
        creation_state = serializer.validated_data.get("state")
        self._check_state_at_creation(creation_state)
        serializer.save()

        if verbose:
            logging.info(f"{TaskService.__name__} created task:\n{serializer.instance}")

    def remove_task(self, instance: Task, force=False):
        if not force and not (
                instance.state in [TaskState.PLANNED, TaskState.FINISHED, TaskState.ARCHIVED]):
            raise ConflictDeletedTaskException()
        if instance.state == TaskState.ACTIVE:
            self.schedules_service.remove_task_schedules(instance)
        instance.delete()
        if verbose:
            logging.info(f"{TaskService.__name__} removed task:\n{instance}")

    def update_task(self, serializer: TaskSerializer, request_method: str):
        instance = serializer.instance
        alternative_state = instance.state if request_method == "PATCH" else Task.state.field.default
        new_state = serializer.validated_data.get("state", alternative_state)
        self._check_and_update_state(instance, new_state, serializer)
        if verbose:
            logging.info(f"{TaskService.__name__} updated task:\n{instance}")

    def set_state_active(self, instance: Task, serializer: TaskSerializer | None = None):
        if not (instance.state in [TaskState.PLANNED, TaskState.PAUSED]):
            raise LogicError()
        self.schedules_service.add_task_schedules(instance)
        if serializer:
            serializer.save()
        else:
            instance.state = TaskState.ACTIVE
            instance.save()
        if verbose:
            logging.info(f"{TaskService.__name__} task has become active:\n{instance}")

    def set_state_paused(self, instance: Task, serializer: TaskSerializer | None = None):
        if instance.state != TaskState.ACTIVE:
            raise LogicError()
        self.schedules_service.remove_task_schedules(instance)
        if serializer:
            serializer.save()
        else:
            instance.state = TaskState.PAUSED
            instance.save()
        if verbose:
            logging.info(f"{TaskService.__name__} task has become paused:\n{instance}")

    def set_state_finished(self, instance: Task, serializer: TaskSerializer | None = None):
        if not (instance.state in [TaskState.ACTIVE, TaskState.PAUSED, TaskState.ARCHIVED]):
            raise LogicError()

        if instance.state == TaskState.ACTIVE:
            self.schedules_service.remove_task_schedules(instance)
            # TODO возможно переделать удаление из БД Schedule
            for schedule in Schedule.objects.filter(task=instance):
                schedule.delete()

        elif instance.state == TaskState.PAUSED:
            # TODO возможно переделать удаление из БД Schedule
            for schedule in Schedule.objects.filter(task=instance):
                schedule.delete()

        if serializer:
            serializer.save()
        else:
            instance.state = TaskState.FINISHED
            instance.save()
        if verbose:
            logging.info(f"{TaskService.__name__} task has become finished:\n{instance}")

    def set_state_archived(self, instance: Task, serializer: TaskSerializer | None = None):
        if instance.state != TaskState.FINISHED:
            raise LogicError()
        if serializer:
            serializer.save()
        else:
            instance.state = TaskState.ARCHIVED
            instance.save()
        if verbose:
            logging.info(f"{TaskService.__name__} task has become archived:\n{instance}")

    def pause_all_tasks(self):
        active_tasks = Task.objects.filter(state=TaskState.ACTIVE)
        for active_task in active_tasks:
            self.set_state_paused(active_task)
        if verbose:
            logging.info(f"{TaskService.__name__} all active tasks have become paused")

    def remove_all_tasks(self, force=False):
        all_tasks = Task.objects.all()
        paused_tasks = list(filter(lambda task: task.state == TaskState.PAUSED, all_tasks))
        active_tasks = list(filter(lambda task: task.state == TaskState.ACTIVE, all_tasks))

        if (paused_tasks or active_tasks) and not force:
            raise ConflictDeletedTaskException()

        for task in all_tasks:
            self.remove_task(task, force=True)
        self.schedules_service.restart_service()
        if verbose:
            logging.info(f"{TaskService.__name__} all tasks tasks have been deleted")

    def _check_and_update_state(self, instance: Task, new_state: TaskState,
                                serializer: TaskSerializer) -> None:
        """
        Checking the possibility of transition to a new state for a task.\n
        Throws exception ConflictTaskStateException if not possible. When an exception is triggered,
        the client is given a response describing the problem and its solution.
        """

        match (instance.state, new_state):
            # no state changes
            case (current_state, new_state) if current_state == new_state:
                serializer.save()
            # possible state changes
            case (TaskState.PLANNED, TaskState.ACTIVE) | (TaskState.PAUSED, TaskState.ACTIVE):
                self.set_state_active(instance, serializer)
            case (TaskState.ACTIVE, TaskState.PAUSED):
                self.set_state_paused(instance, serializer)
            case (TaskState.ACTIVE, TaskState.FINISHED) | (TaskState.PAUSED, TaskState.FINISHED) | (
                TaskState.ARCHIVED, TaskState.FINISHED):
                self.set_state_finished(instance, serializer)
            case (TaskState.FINISHED, TaskState.ARCHIVED):
                self.set_state_archived(instance, serializer)
            # impossible state changes
            case _:
                raise ConflictTaskStateException(instance.state)

    def _check_state_at_creation(self, state: TaskState | None = None) -> None:
        """
        Checks the client-specified state of the task when it is created.\n
        Throws an exception ConflictTaskStateAtCreationException if an invalid state is specified.
        When an exception is triggered, the client is given a response describing
        the problem and its solution.
        """
        if state is None:
            return
        if state != TaskState.PLANNED:
            raise ConflictTaskStateAtCreationException()
