from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .errors import RequiredFieldsMissing, ValidationFailed
from .serializers import (
    WorkVolumeRequestSerializer,
    WorkVolumeResponseSerializer,
    check_required_fields,
)


class WorkVolumeListView(APIView):
    http_method_names = ["post", "options"]

    def post(self, request):
        data = request.data
        if not isinstance(data, dict):
            raise ValidationFailed("Request body must be a JSON object")

        missing = check_required_fields(data)
        if missing:
            raise RequiredFieldsMissing(details={"missing": missing})

        serializer = WorkVolumeRequestSerializer(data=data)
        if not serializer.is_valid():
            raise ValidationFailed(details=serializer.errors)
        v = serializer.validated_data

        work_volume = services.save_work_volume(
            user=request.user,
            factory_id=v["factory"],
            start=v["start"],
            finish=v["finish"],
            weight=v["weight"],
            author_id=v["author"],
        )
        return Response(
            WorkVolumeResponseSerializer(work_volume).data, status=status.HTTP_201_CREATED
        )
