from django.conf import settings
from rest_framework import status
from rest_framework.response import Response


class CustomResponse(Response):
    @classmethod
    def success(cls, message, data=None, status_code=status.HTTP_200_OK):
        response_data = {"success": True, "message": message, "data": data}
        return cls(response_data, status=status_code)

    @classmethod
    def error(cls, message, data=None, status_code=status.HTTP_400_BAD_REQUEST):
        response_data = {
            "success": False,
            "message": message,
            "data": data,
        }
        return cls(response_data, status=status_code)
    

