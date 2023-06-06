import datetime
import pytest
import factory
from pytest_factoryboy import register

from tasks.models import Task, Subject, Schedule
from tasks.services.task_service import TaskService


def setup_test_environment():
    factory.random.reseed_random('simplytimemanager')


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def clear_context():
    yield
    TaskService().remove_all_tasks(force=True)


class SubjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Subject

    title = factory.Sequence(lambda n: f'Subject {n}')


class ScheduleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Schedule

    start_time = datetime.time(10, 00)
    end_time = datetime.time(12, 00)


register(SubjectFactory)
register(ScheduleFactory)
