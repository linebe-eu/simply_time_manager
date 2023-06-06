from rest_framework.serializers import ModelSerializer
from tasks.models import *


class TaskSerializer(ModelSerializer):
    class Meta:
        model = Task
        fields = "__all__"


class SubjectSerializer(ModelSerializer):
    class Meta:
        model = Subject
        fields = "__all__"


class ScheduleSerializer(ModelSerializer):
    class Meta:
        model = Schedule
        fields = "__all__"
