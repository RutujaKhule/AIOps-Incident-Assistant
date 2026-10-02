import os


AI_PROVIDER = os.getenv("AI_PROVIDER", "mock").strip().lower() or "mock"


def _read_positive_int(name, default, minimum=1):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be an integer.") from error
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return value


AI_MAX_METRICS = _read_positive_int("AI_MAX_METRICS", 30)
AI_MAX_LOGS = _read_positive_int("AI_MAX_LOGS", 10)
AI_MAX_CONTEXT_CHARS = _read_positive_int("AI_MAX_CONTEXT_CHARS", 12000, minimum=512)

if AI_PROVIDER != "mock":
    raise ValueError("Only AI_PROVIDER=mock is currently supported. No API key is required.")