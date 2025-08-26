from rest_framework import serializers, status
from rest_framework.exceptions import APIException


class PlainValidationError(APIException):
    """
    :In PlainValidationError, we will check if the exception being raised is of
    the type dict and then modify the errors format and return that modified errors response
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid input."
    default_code = "invalid"

    def __init__(self, detail=None, code=None):
        if not isinstance(detail, dict):
            raise serializers.ValidationError("Invalid Input")
        self.detail = detail