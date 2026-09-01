import logging

from app.core.logging import configure_logging


def test_http_client_request_details_are_not_logged_at_info() -> None:
    configure_logging("INFO")

    assert logging.getLogger("httpx").getEffectiveLevel() == logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() == logging.WARNING