from django.db import models
from django.db.models import Q, F


# TODO Need to add internalization
# TODO Need to add test of models
# TODO Need to add Schedule Logic

class Subject(models.Model):
    title = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return f"{self.title} (id={self.id})"


class TaskState(models.TextChoices):
    PLANNED = 'planned'
    ACTIVE = 'active'
    PAUSED = 'paused'
    FINISHED = 'finished'
    ARCHIVED = 'archived'

    @classmethod
    def get_state_at_creation(cls):
        return cls.PLANNED

    @classmethod
    def get_incorrect_states_at_creation(cls):
        incorrect_states: list['TaskState'] = cls.values
        incorrect_states.remove(cls.get_state_at_creation())
        return incorrect_states


class Task(models.Model):
    title = models.CharField(max_length=64)
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, null=True, related_name="tasks",
                                to_field="title")
    description = models.TextField(blank=True)
    state = models.CharField(choices=TaskState.choices, default=TaskState.get_state_at_creation(),
                             max_length=8)
    time_create = models.DateTimeField(auto_now_add=True)
    time_update = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} id:{self.pk} [{self.state}]"


class Schedule(models.Model):
    task = models.ForeignKey(Task,
                             on_delete=models.CASCADE,
                             related_name="schedules")
    start_time = models.TimeField()
    end_time = models.TimeField()
    monday = models.BooleanField(default=False)
    tuesday = models.BooleanField(default=False)
    wednesday = models.BooleanField(default=False)
    thursday = models.BooleanField(default=False)
    friday = models.BooleanField(default=False)
    saturday = models.BooleanField(default=False)
    sunday = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(name="must_be_least_one_weekday",
                                   check=Q(monday=True) |
                                         Q(tuesday=True) |
                                         Q(wednesday=True) |
                                         Q(thursday=True) |
                                         Q(friday=True) |
                                         Q(saturday=True) |
                                         Q(sunday=True)),
            models.CheckConstraint(name="start_time_must_be_before_end_time",
                                   check=Q(start_time__lt=F("end_time"))),
        ]

    @property
    def is_on_weekdays(self) -> bool | None:
        if all((self.monday, self.tuesday, self.wednesday, self.thursday, self.friday)):
            return True
        elif any((self.monday, self.tuesday, self.wednesday, self.thursday, self.friday)):
            return None
        return False

    @property
    def is_on_weekends(self) -> bool | None:
        if all((self.saturday, self.sunday)):
            return True
        if any((self.saturday, self.sunday)):
            return None
        return False

    @property
    def is_every_day(self) -> bool:
        if self.is_on_weekdays and self.is_on_weekends:
            return True
        return False

    @property
    def weekdays(self) -> list[tuple[str, bool]]:
        """
        Returns a list of pairs: the name of the day of the week and its presence in the schedule
        :return:
        """
        return [(str(Schedule.monday.field.name).capitalize(), bool(self.monday)),
                (str(Schedule.tuesday.field.name).capitalize(), bool(self.tuesday)),
                (str(Schedule.wednesday.field.name).capitalize(), bool(self.wednesday)),
                (str(Schedule.thursday.field.name).capitalize(), bool(self.thursday)),
                (str(Schedule.friday.field.name).capitalize(), bool(self.friday)),
                (str(Schedule.saturday.field.name).capitalize(), bool(self.saturday)),
                (str(Schedule.sunday.field.name).capitalize(), bool(self.sunday)),
                ]

    def __str__(self):
        # TODO: make another implementation, not very clean
        return_prefix = f" {self.task.title} "
        return_suffix = f" at {self.start_time} - {self.end_time} [{self.task.state}]"
        is_on_weekdays = self.is_on_weekdays
        is_on_weekends = self.is_on_weekends
        if is_on_weekdays and is_on_weekends:
            return return_prefix + "every day" + return_suffix
        elif is_on_weekdays and is_on_weekends is False:
            return return_prefix + "on weekdays" + return_suffix
        elif is_on_weekends and is_on_weekdays is False:
            return return_prefix + "on weekends" + return_suffix
        else:
            weekdays = self.weekdays

            active_weekdays = tuple(weekday for weekday, is_ in weekdays if is_)
            nonactive_weekdays = tuple(weekday for weekday, is_ in weekdays if not is_)

            if len(active_weekdays) > len(nonactive_weekdays) + 1:
                return return_prefix + f"every day except {' and '.join(nonactive_weekdays)}" + return_suffix
            else:
                return return_prefix + f"on {'s, '.join(active_weekdays)}s" + return_suffix


class Report(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="reports")
    text = models.TextField()
    time_create = models.DateTimeField(auto_now_add=True)
    time_update = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{Report.__name__} id:{self.id} task:{self.task.title}"


class Note(models.Model):
    # TODO Make it possible to attach files to notes
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="notes")
    title = models.CharField(max_length=64, default="No Title")
    text = models.TextField()
    time_create = models.DateTimeField(auto_now_add=True)
    time_update = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{Note.__name__} id:{self.id} task:{self.task.title}"


class ToDo(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, null=True, related_name="todos")
    text = models.TextField()

    class Meta:
        verbose_name = "ToDo"
        verbose_name_plural = "ToDos"

    def __str__(self):
        return f"{ToDo.__name__}  id:{self.id} subject:{self.subject.title}"
