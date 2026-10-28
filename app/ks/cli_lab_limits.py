"""Length limits shared by planning, caption alignment and refresh."""
MIN_SECONDS = 5
MAX_SECONDS = 600


def audio_timeout(duration):
    return max(120, min(600, round(duration)))
