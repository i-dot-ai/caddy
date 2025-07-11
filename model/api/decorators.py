import functools
import time


def retry(
    logger_attr="logger",
    num_retries=3,
    delay=1,
    backoff=2,
    exceptions=(Exception,),
):
    """
    Retry decorator

    Parameters:
    logger_attr (str): Name of the logger attribute on the instance
    num_retries (int): Number of times to retry before giving up
    delay (int): Initial delay between retries in seconds
    backoff (int): Factor by which the delay should be multiplied each retry
    exceptions (tuple): Exceptions to trigger a retry
    """

    def decorator_retry(func):
        @functools.wraps(func)
        def wrapper_retry(*args, **kwargs):
            _num_retries, _delay = num_retries, delay
            instance = args[0] if args else None
            struct_logger = getattr(instance, logger_attr, None) if instance else None
            while _num_retries > 0:
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    _num_retries -= 1
                    if _num_retries == 0:
                        raise
                    time.sleep(_delay)
                    _delay *= backoff
                    if struct_logger:
                        struct_logger.exception(
                            "Retrying {num_retries} more times after exception",
                            num_retries=_num_retries,
                        )

        return wrapper_retry

    return decorator_retry
