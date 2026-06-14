import logging
import re

_TOKEN_QUERY_RE = re.compile(r"([?&]token=)[^&\s]+")


def redact_query_tokens(value: str) -> str:
    return _TOKEN_QUERY_RE.sub(r"\1<redacted>", value)


class QueryTokenRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_query_tokens(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact_query_tokens(arg) if isinstance(arg, str) else arg for arg in record.args)
        elif isinstance(record.args, dict):
            record.args = {
                key: redact_query_tokens(value) if isinstance(value, str) else value
                for key, value in record.args.items()
            }
        return True


def install_query_token_redaction() -> None:
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, QueryTokenRedactionFilter) for item in logger.filters):
        logger.addFilter(QueryTokenRedactionFilter())
