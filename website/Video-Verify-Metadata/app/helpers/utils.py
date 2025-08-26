from datetime import datetime


def convert_unix_to_utc(unix_timestamp):
    """
    Converts a UNIX timestamp to a UTC datetime string.

    :param unix_timestamp: int, The UNIX timestamp to convert.
    :return: str, The converted date and time in UTC.
    """
    return datetime.utcfromtimestamp(unix_timestamp).strftime("%Y-%m-%d %H:%M:%S UTC")
