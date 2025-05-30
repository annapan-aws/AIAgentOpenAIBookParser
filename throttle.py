import time
import random
import openai

def exponential_backoff(
    func,
    max_retries=5,
    base_delay=1.0,
    max_delay=30.0,
    retryable_errors=(openai.RateLimitError, openai.APIError)
):
    for attempt in range(max_retries):
        try:
            return func()
        except retryable_errors as e:
            sleep_time = min(max_delay, base_delay * (2 ** attempt)) + random.uniform(0, 1)
            print(f"Retry {attempt + 1}/{max_retries} after {sleep_time:.2f}s due to: {e}")
            time.sleep(sleep_time)
    raise RuntimeError(f"Exceeded max retries ({max_retries})")
