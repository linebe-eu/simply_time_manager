import datetime
import pytest

from django.urls import reverse
from rest_framework import status
from task.models import TaskState
from task.serializers import TaskSerializer
from task.services.exceptions import ConflictTaskStateAtCreationException, \
    ConflictActiveTaskSchedulesMissingException, ConflictActiveTaskSchedulesException, \
    ConflictTaskStateException, \
    ConflictDeletedTaskException
from task.services.task_service import TaskService


@pytest.mark.django_db
@pytest.mark.parametrize('task_data', [
    pytest.param(
        {"title": "Task",
         "subject": "Subject",  # in runtime replace real subject
         "description": "Task description",
         "state": TaskState.get_state_at_creation(),
         },
        id="task data",
    ),
    pytest.param(
        {"title": "Task",
         "subject": "Subject",  # in runtime replace real subject
         "description": "Created task description",
         },
        id="task data wo state",
    ),
    pytest.param(
        {"title": "Task",
         "description": "Created task description",
         },
        id="task dataa wo state and subject",
    ),
    pytest.param(
        {"title": "Created task",
         },
        id="task data only title",
    ),
])
def test_get_task(task_data, api_client, subject_factory, task_factory):
    if task_data.get("subject", None):
        task_data["subject"] = subject_factory(title=task_data["subject"])

    task = task_factory(**task_data)
    url = reverse('tasks-detail', kwargs={'pk': task.pk})
    response = api_client.get(url)

    assert status.HTTP_200_OK == response.status_code
    serializer_data = TaskSerializer(task).data
    assert serializer_data == response.data


@pytest.mark.django_db
@pytest.mark.parametrize('tasks_data', [
    pytest.param(
        [
            {"title": "Task1",
             "subject": "Subject1",  # in runtime replace real subject
             "description": "Task1 description",
             "state": TaskState.get_state_at_creation(),
             },
            {"title": "Task2",
             "subject": "Subject2",  # in runtime replace real subject
             "description": "Task2 description",
             "state": TaskState.get_state_at_creation(),
             },
            {"title": "Task3",
             "subject": "Subject3",  # in runtime replace real subject
             "description": "Task3 description",
             "state": TaskState.get_state_at_creation(),
             },
        ],

        id="more tasks",
    ),
    pytest.param(
        [],
        id="no tasks",
    ),
])
def test_get_tasks(tasks_data, api_client, subject_factory, task_factory):
    tasks = []
    for task_data in tasks_data:
        if task_data.get("subject", None):
            task_data["subject"] = subject_factory(title=task_data["subject"])
        tasks.append(task_factory(**task_data))

    url = reverse('tasks-list')
    response = api_client.get(url)

    assert status.HTTP_200_OK == response.status_code
    serializer_data = TaskSerializer(tasks, many=True).data
    assert serializer_data == response.data


@pytest.mark.django_db
@pytest.mark.parametrize('request_data,expected_conflict', [
    pytest.param(
        {"title": "Created task",
         "subject": "Subject",  # in runtime replace real subject
         "description": "Created task description",
         "state": TaskState.get_state_at_creation(),
         },
        None,
        id="request_data",
    ),
    pytest.param(
        {"title": "Created task",
         "subject": "Subject",  # in runtime replace real subject
         "description": "Created task description",
         },
        None,
        id="request_data wo state",
    ),
    pytest.param(
        {"title": "Created task",
         "description": "Created task description",
         },
        None,
        id="request_data wo state and subject",
    ),
    pytest.param(
        {"title": "Created task",
         },
        None,
        id="request_data only title",
    ),
    pytest.param(
        {"title": "No created task",
         "subject": "Subject",  # in runtime replace real subject
         "description": "No created task description",
         "state": TaskState.ACTIVE,
         },
        ConflictTaskStateAtCreationException(),
        id=f"NEGATIVE request_data with bad state {TaskState.ACTIVE}",
    ),
    pytest.param(
        {"title": "No created task",
         "subject": "Subject",  # in runtime replace real subject
         "description": "No created task description",
         "state": TaskState.PAUSED,
         },
        ConflictTaskStateAtCreationException(),
        id=f"NEGATIVE request_data with bad state {TaskState.PAUSED}",
    ),
    pytest.param(
        {"title": "No created task",
         "subject": "Subject",  # in runtime replace real subject
         "description": "No created task description",
         "state": TaskState.FINISHED,
         },
        ConflictTaskStateAtCreationException(),
        id=f"NEGATIVE request_data with bad state {TaskState.FINISHED}",
    ),
    pytest.param(
        {"title": "No created task",
         "subject": "Subject",  # in runtime replace real subject
         "description": "No created task description",
         "state": TaskState.ARCHIVED,
         },
        ConflictTaskStateAtCreationException(),
        id=f"NEGATIVE request_data with bad state {TaskState.ARCHIVED}",
    ),
])
def test_create_task(request_data, api_client, subject_factory, expected_conflict, clear_context):
    if request_data.get("subject", None):
        request_data["subject"] = subject_factory(title=request_data["subject"]).title

    url = reverse('tasks-list')
    response = api_client.post(url, data=request_data)

    if expected_conflict:
        assert expected_conflict.status_code == response.status_code
        assert expected_conflict.detail == response.data['detail']
    else:
        assert status.HTTP_201_CREATED == response.status_code
        expected_response_data: dict = request_data.copy()
        expected_response_data.update(state=TaskState.get_state_at_creation(),
                                      subject=request_data.get("subject", None),
                                      description=request_data.get("description", ""),
                                      id=response.data["id"],
                                      time_create=response.data["time_create"],
                                      time_update=response.data["time_update"],
                                      )
        assert expected_response_data == response.data


@pytest.mark.django_db
@pytest.mark.parametrize('from_state,expected_conflict', [
    pytest.param(
        TaskState.PLANNED,
        None,
        id=f"from {TaskState.PLANNED}",
    ),
    pytest.param(
        TaskState.FINISHED,
        None,
        id=f"from {TaskState.FINISHED}",
    ),
    pytest.param(
        TaskState.ARCHIVED,
        None,
        id=f"from {TaskState.ARCHIVED}",
    ),
    pytest.param(
        TaskState.ACTIVE,
        ConflictDeletedTaskException(),
        id=f"NEGATIVE from {TaskState.ACTIVE}",
    ),
    pytest.param(
        TaskState.PAUSED,
        ConflictDeletedTaskException(),
        id=f"NEGATIVE from {TaskState.PAUSED}",
    ),
])
def test_delete_task(api_client, task_factory, schedule_factory, from_state, expected_conflict,
                     clear_context):
    task = task_factory()
    schedule_factory(task=task, monday=True)
    if from_state == TaskState.ACTIVE:
        TaskService().set_state_active(task)
    if from_state == TaskState.PAUSED:
        TaskService().set_state_active(task)
        TaskService().set_state_paused(task)
    if from_state == TaskState.FINISHED:
        TaskService().set_state_active(task)
        TaskService().set_state_finished(task)
    if from_state == TaskState.ARCHIVED:
        TaskService().set_state_active(task)
        TaskService().set_state_finished(task)
        TaskService().set_state_archived(task)

    url = reverse('tasks-detail', kwargs={'pk': task.pk})
    response = api_client.delete(url)

    if expected_conflict:
        assert expected_conflict.status_code == response.status_code
        assert expected_conflict.detail == response.data['detail']
    else:
        assert status.HTTP_204_NO_CONTENT == response.status_code


@pytest.mark.django_db
@pytest.mark.parametrize('request_method,request_data', [
    pytest.param(
        "PUT",
        {"title": "Changed task title",
         "description": "Changed task description"},
        id="PUT request_data wo subject",
    ),
    pytest.param(
        "PATCH",
        {},
        id="PATCH request_data only state",
    ),
])
class TestsChangingTaskState:

    @pytest.fixture(autouse=True)
    def set_class_attributes(self, api_client, request_method, request_data, task_factory,
                             schedule_factory):
        self.request_data = request_data
        if request_method == "PUT":
            self.client_change_request = lambda path, data: api_client.put(path, data=data)
        if request_method == "PATCH":
            self.client_change_request = lambda path, data: api_client.patch(path, data=data)
        self.task_factory = task_factory
        self.schedule_factory = schedule_factory

    def teardown_method(self, method):
        TaskService().remove_all_tasks(force=True)

    @pytest.mark.parametrize('my_schedules,other_schedules,expected_conflict', [
        pytest.param(
            [
                {"start_time": datetime.time(10, 00),
                 "end_time": datetime.time(12, 00),
                 "monday": True},
                {"start_time": datetime.time(8, 00),
                 "end_time": datetime.time(10, 00),
                 "tuesday": True, "wednesday": True},
            ],
            [],
            None,
            id="wo other active tasks",
        ),
        pytest.param(
            [
                {"start_time": datetime.time(10, 00),
                 "end_time": datetime.time(12, 00),
                 "monday": True},
                {"start_time": datetime.time(8, 00),
                 "end_time": datetime.time(10, 00),
                 "tuesday": True, "wednesday": True},
            ],
            [
                {"start_time": datetime.time(12, 00),
                 "end_time": datetime.time(14, 00),
                 "monday": True},
                {"start_time": datetime.time(8, 00),
                 "end_time": datetime.time(10, 00),
                 "saturday": True, "sunday": True},
            ],
            None,
            id="with other active tasks",
        ),
        pytest.param(
            [],
            [],
            ConflictActiveTaskSchedulesMissingException(),
            id="NEGATIVE wo schedules",
        ),
        pytest.param(
            [
                {"start_time": datetime.time(10, 00),
                 "end_time": datetime.time(12, 00),
                 "monday": True},
                {"start_time": datetime.time(8, 00),
                 "end_time": datetime.time(10, 00),
                 "tuesday": True, "wednesday": True},
            ],
            [
                {"start_time": datetime.time(11, 00),
                 "end_time": datetime.time(13, 00),
                 "monday": True},
            ],
            ConflictActiveTaskSchedulesException(),
            id="NEGATIVE conflict with other active tasks",
        ),

    ])
    def test_from_planned_to_active(self, my_schedules, other_schedules, expected_conflict):
        # prepare active tasks if they're exists in test parameters
        for schedule in other_schedules:
            task = self.task_factory()
            self.schedule_factory(task=task, **schedule)
            TaskService().set_state_active(task)

        planned_task = self.task_factory()
        for schedule in my_schedules:
            self.schedule_factory(task=planned_task, **schedule)

        url = reverse('tasks-detail', kwargs={'pk': planned_task.pk})
        self.request_data["state"] = TaskState.ACTIVE
        response = self.client_change_request(url, data=self.request_data)

        if expected_conflict:
            assert expected_conflict.status_code == response.status_code
            assert expected_conflict.detail == response.data['detail']
        else:
            assert status.HTTP_200_OK == response.status_code

            expected_response_data: dict = self.request_data.copy()
            expected_response_data.update(state=TaskState.ACTIVE,
                                          title=self.request_data.get("title",
                                                                      planned_task.title),
                                          subject=self.request_data.get("subject",
                                                                        planned_task.subject),
                                          description=self.request_data.get("description",
                                                                            planned_task.description),
                                          id=planned_task.pk,
                                          time_create=response.data["time_create"],
                                          time_update=response.data["time_update"],
                                          )

            assert expected_response_data == response.data

    @pytest.mark.parametrize('my_schedules,other_schedules,expected_conflict', [
        pytest.param(
            [
                {"start_time": datetime.time(10, 00),
                 "end_time": datetime.time(12, 00),
                 "monday": True},
                {"start_time": datetime.time(8, 00),
                 "end_time": datetime.time(10, 00),
                 "tuesday": True, "wednesday": True},
            ],
            [],
            None,
            id="wo other active tasks",
        ),
        pytest.param(
            [
                {"start_time": datetime.time(10, 00),
                 "end_time": datetime.time(12, 00),
                 "monday": True},
                {"start_time": datetime.time(8, 00),
                 "end_time": datetime.time(10, 00),
                 "tuesday": True, "wednesday": True},
            ],
            [
                {"start_time": datetime.time(12, 00),
                 "end_time": datetime.time(14, 00),
                 "monday": True},
                {"start_time": datetime.time(8, 00),
                 "end_time": datetime.time(10, 00),
                 "saturday": True, "sunday": True},
            ],
            None,
            id="with other active tasks",
        ),
        pytest.param(
            [
                {"start_time": datetime.time(10, 00),
                 "end_time": datetime.time(12, 00),
                 "monday": True},
                {"start_time": datetime.time(8, 00),
                 "end_time": datetime.time(10, 00),
                 "tuesday": True, "wednesday": True},
            ],
            [
                {"start_time": datetime.time(11, 00),
                 "end_time": datetime.time(13, 00),
                 "monday": True},
            ],
            ConflictActiveTaskSchedulesException(),
            id="NEGATIVE conflict with other active tasks",
        ),

    ])
    def test_from_paused_to_active(self, my_schedules, other_schedules, expected_conflict):

        paused_task = self.task_factory()
        for schedule in my_schedules:
            self.schedule_factory(task=paused_task, **schedule)
        TaskService().set_state_active(paused_task)
        TaskService().set_state_paused(paused_task)

        # prepare active tasks if they're exists in test parameters
        for schedule in other_schedules:
            task = self.task_factory()
            self.schedule_factory(task=task, **schedule)
            TaskService().set_state_active(task)

        url = reverse('tasks-detail', kwargs={'pk': paused_task.pk})
        self.request_data["state"] = TaskState.ACTIVE
        response = self.client_change_request(url, data=self.request_data)

        if expected_conflict:
            assert expected_conflict.status_code == response.status_code
            assert expected_conflict.detail == response.data['detail']
        else:
            assert status.HTTP_200_OK == response.status_code

            expected_response_data: dict = self.request_data.copy()
            expected_response_data.update(state=TaskState.ACTIVE,
                                          title=self.request_data.get("title",
                                                                      paused_task.title),
                                          subject=self.request_data.get("subject",
                                                                        paused_task.subject),
                                          description=self.request_data.get("description",
                                                                            paused_task.description),
                                          id=paused_task.pk,
                                          time_create=response.data["time_create"],
                                          time_update=response.data["time_update"],
                                          )

            assert expected_response_data == response.data

    @pytest.mark.parametrize('from_,to', [
        pytest.param(
            TaskState.PLANNED,
            TaskState.PAUSED,
        ),
        pytest.param(
            TaskState.PLANNED,
            TaskState.FINISHED,
        ),
        pytest.param(
            TaskState.PLANNED,
            TaskState.ARCHIVED,
        ),
        pytest.param(
            TaskState.ACTIVE,
            TaskState.PLANNED,
        ),
        pytest.param(
            TaskState.ACTIVE,
            TaskState.ARCHIVED,
        ),
        pytest.param(
            TaskState.PAUSED,
            TaskState.PLANNED,
        ),
        pytest.param(
            TaskState.PAUSED,
            TaskState.ARCHIVED,
        ),

        pytest.param(
            TaskState.FINISHED,
            TaskState.PLANNED,
        ),
        pytest.param(
            TaskState.FINISHED,
            TaskState.ACTIVE,
        ),
        pytest.param(
            TaskState.FINISHED,
            TaskState.PAUSED,
        ),

        pytest.param(
            TaskState.ARCHIVED,
            TaskState.PLANNED,
        ),
        pytest.param(
            TaskState.ARCHIVED,
            TaskState.ACTIVE,
        ),
        pytest.param(
            TaskState.ARCHIVED,
            TaskState.PAUSED,
        ),

    ])
    def test_negative_from_any_to_impossible_state(self, from_, to):
        task = self.task_factory()
        self.schedule_factory(task=task, monday=True)
        if from_ == TaskState.ACTIVE:
            TaskService().set_state_active(task)
        if from_ == TaskState.PAUSED:
            TaskService().set_state_active(task)
            TaskService().set_state_paused(task)
        if from_ == TaskState.FINISHED:
            TaskService().set_state_active(task)
            TaskService().set_state_finished(task)
        if from_ == TaskState.ARCHIVED:
            TaskService().set_state_active(task)
            TaskService().set_state_finished(task)
            TaskService().set_state_archived(task)

        url = reverse('tasks-detail', kwargs={'pk': task.pk})

        self.request_data["state"] = to
        expected_conflict = ConflictTaskStateException(from_)

        response = self.client_change_request(url, self.request_data)

        assert expected_conflict.status_code == response.status_code
        assert expected_conflict.detail == response.data['detail']
