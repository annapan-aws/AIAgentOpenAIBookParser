import time
import random
import botocore.exceptions  # or openai.error.* if using OpenAI

def exponential_backoff(
    func,                # your function to call (e.g., model invocation)
    max_retries=5,       # max number of retries
    base_delay=1.0,      # initial wait time in seconds
    max_delay=30.0,      # max delay cap
    retryable_errors=(botocore.exceptions.ClientError,)  # customize as needed
):
    for attempt in range(max_retries):
        try:
            return func()  # call your function
        except retryable_errors as e:
            # Check for throttling or token-related errors (customize as needed)
            if hasattr(e, "response"):
                code = e.response["Error"]["Code"]
                if code != "ThrottlingException":
                    raise  # re-raise non-throttling errors

            # Wait with exponential backoff + jitter
            sleep_time = min(max_delay, base_delay * (2 ** attempt)) + random.uniform(0, 1)
            print(f"Retry {attempt+1}/{max_retries} after {sleep_time:.2f}s due to: {e}")
            time.sleep(sleep_time)

    raise RuntimeError(f"Exceeded max retries ({max_retries})")
