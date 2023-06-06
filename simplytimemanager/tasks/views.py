from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .serializers import *
from .models import *
from .services.task_service import TaskService


class TaskViewSet(ModelViewSet):
    serializer_class = TaskSerializer
    queryset = Task.objects.all()

    def create(self, request, *args, **kwargs):
        TaskService().create_task(**request.data.dict())

        serializer_data = TaskService().last_task_serializer.data
        headers = self.get_success_headers(serializer_data)
        return Response(serializer_data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        TaskService().update_task(instance, partial, **request.data.dict())
        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        serializer_data = TaskService().last_task_serializer.data
        return Response(serializer_data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        TaskService().remove_task(instance)

        return Response(status=status.HTTP_204_NO_CONTENT)


class SubjectViewSet(ModelViewSet):
    serializer_class = SubjectSerializer
    queryset = Subject.objects.all()


class ScheduleViewSet(ModelViewSet):
    serializer_class = ScheduleSerializer
    queryset = Schedule.objects.all()
