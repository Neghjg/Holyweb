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

    def initial(self, request, *args, **kwargs):
        # D5: authentication (401/900) goes before content negotiation (406/907).
        self.perform_authentication(request)
        self.check_permissions(request)
        super().initial(request, *args, **kwargs)

    def post(self, request):
        try:
            data = request.data
        except RecursionError:  # absurdly nested JSON is not a ValueError for the parser
            raise ValidationFailed("Request body is nested too deeply") from None
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
