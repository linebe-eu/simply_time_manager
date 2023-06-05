from django.urls import path, include
from rest_framework import routers

from task.views import *

router = routers.DefaultRouter()
router.register("tasks", TaskViewSet, basename="tasks")
router.register("subjects", SubjectViewSet, basename="subjects")
router.register("schedules", ScheduleViewSet, basename="schedules")

urlpatterns = [
    path("", include(router.urls)),
]
