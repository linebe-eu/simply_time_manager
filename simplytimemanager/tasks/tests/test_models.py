from datetime import time
import pytest
from django.db import IntegrityError

from tasks.models import Task, Subject, Schedule, TaskState


@pytest.mark.django_db
class TestsTaskModel:

    @pytest.mark.parametrize('field_name', ['title',
                                            'subject',
                                            'description',
                                            'state',
                                            'time_create',
                                            'time_update',
                                            ])
    def test_field_label(self, field_name):
        created_task = Task.objects.create(title='Task')
        task = Task.objects.get(id=created_task.pk)
        field_label = task._meta.get_field(field_name).verbose_name
        expected_field_label = str(field_label).replace('_', ' ')
        assert expected_field_label == field_label

    @pytest.mark.parametrize('field_name,max_length', [('title', 64),
                                                       ('state', 8)])
    def test_field_max_length(self, field_name, max_length):
        created_task = Task.objects.create(title='Task')
        task = Task.objects.get(id=created_task.pk)

        current_max_length = task._meta.get_field(field_name).max_length
        assert max_length == current_max_length

    @pytest.mark.parametrize('field_name,default_value', [('state', TaskState.PLANNED),
                                                          ('description', '')])
    def test_field_max_length_default_value(self, field_name, default_value):
        created_task = Task.objects.create(title='Task')
        task = Task.objects.get(id=created_task.pk)

        field_default = task._meta.get_field(field_name).default
        assert default_value == field_default
        assert default_value == getattr(task, field_name)

    def test_str_method(self):
        created_task = Task.objects.create(title='Task')
        task = Task.objects.get(id=created_task.pk)

        assert f"{task.title} id:{task.pk} [{task.state}]" == str(task)


@pytest.mark.django_db
class TestsSubjectModel:
    @pytest.mark.parametrize('field_name', ['title'])
    def test_field_label(self, field_name):
        created_subject = Subject.objects.create(title='Subject')
        subject = Subject.objects.get(id=created_subject.pk)
        field_label = subject._meta.get_field(field_name).verbose_name
        expected_field_label = str(field_label).replace('_', ' ')
        assert expected_field_label == field_label

    @pytest.mark.parametrize('field_name,max_length', [('title', 64)])
    def test_field_max_length(self, field_name, max_length):
        created_subject = Subject.objects.create(title='Subject')
        subject = Subject.objects.get(id=created_subject.pk)
        current_max_length = subject._meta.get_field(field_name).max_length
        assert max_length == current_max_length

    def test_unique_title(self):
        title = 'Subject'
        Subject.objects.create(title=title)
        with pytest.raises(IntegrityError):
            Subject.objects.create(title=title)

    def test_str_method(self):
        created_subject = Subject.objects.create(title='Subject')
        subject = Subject.objects.get(id=created_subject.pk)
        assert f"{subject.title} (id={subject.pk})" == str(subject)


@pytest.mark.django_db
class TestsScheduleModel:
    @pytest.mark.parametrize('field_name', ['task',
                                            'start_time',
                                            'end_time',
                                            'monday',
                                            'tuesday',
                                            'wednesday',
                                            'thursday',
                                            'friday',
                                            'saturday',
                                            'sunday'])
    def test_field_label(self, field_name):
        task = Task.objects.create(title='Task')
        created_schedule = Schedule.objects.create(task=task,
                                                   monday=True,
                                                   start_time=time(10, 00),
                                                   end_time=time(12, 00))

        schedule = Schedule.objects.get(id=created_schedule.pk)

        field_label = schedule._meta.get_field(field_name).verbose_name
        expected_field_label = str(field_label).replace('_', ' ')
        assert expected_field_label == field_label

    def test_str_method(self):
        ...
        # TODO write test
