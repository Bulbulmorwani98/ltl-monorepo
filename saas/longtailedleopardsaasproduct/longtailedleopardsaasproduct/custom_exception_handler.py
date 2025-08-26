from rest_framework import status
from rest_framework.views import exception_handler

from apps.accounts import models as account_models


def custom_exception_handler(exc, context):
    # Call the default exception handler first
    response = exception_handler(exc, context)
    if response is not None:
        # Customize the response format
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            response.data = {
                "success": False,
                "message": "Authentication credentials were not provided.",
                "data": None,
            }
        elif response.status_code == status.HTTP_403_FORBIDDEN:
            response.data = {
                "success": False,
                "message": "You do not have permission to perform this action.",
                "data": None,
            }
        else:
            # Fallback for other exceptions
            response.data = {
                "success": False,
                "message": str(exc),
                "data": None,
            }

    return response


def load_configuration():
    try:
        conf_list = account_models.Configuration.scan()
        CONF_DATA = conf_list.next()
        return CONF_DATA.data[0]
    except Exception as e:
        return None
