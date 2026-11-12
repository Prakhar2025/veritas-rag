"""Bedrock chat provider over the Converse API with retries and spend metering."""

from __future__ import annotations

import random
import time

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from botocore.exceptions import ConnectionError as BotocoreConnectionError

from app.core.spend import SpendMeter
from app.providers.base import ChatResult

RETRYABLE_CODES = {
    "ThrottlingException",
    "ServiceUnavailableException",
    "InternalServerError",
    "ModelErrorException",
    "ModelStreamErrorException",
}
MAX_ATTEMPTS = 4
BACKOFF_BASE_SECONDS = 1.0


class BedrockChat:
    """Converse API wrapper. One instance, one region, one meter."""

    def __init__(self, region: str, profile: str, meter: SpendMeter) -> None:
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        self._client = session.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(read_timeout=90, retries={"max_attempts": 0}),
        )
        self._meter = meter

    def complete(
        self,
        purpose: str,
        model_id: str,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float = 0.0,
    ) -> ChatResult:
        """Run one converse call with retries, metering spend against the cap."""
        # Conservative cap check: assume the user prompt is the input size.
        self._meter.check_headroom(self._meter.price_for(model_id)[0] * len(user) / 4)
        last_error: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = self._client.converse(
                    modelId=model_id,
                    system=[{"text": system}] if system else None,
                    messages=[{"role": "user", "content": [{"text": user}]}],
                    inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
                )
                break
            except (ClientError, BotocoreConnectionError) as exc:  # noqa: PERF203
                code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
                retryable = isinstance(exc, BotocoreConnectionError) or code in RETRYABLE_CODES
                if attempt == MAX_ATTEMPTS - 1 or not retryable:
                    last_error = exc
                    break
                delay = BACKOFF_BASE_SECONDS * (2**attempt) + random.uniform(0, 0.5)
                time.sleep(delay)
                last_error = None
        if last_error is not None:
            raise RuntimeError(
                f"bedrock converse failed after retries: {last_error}"
            ) from last_error

        output = response["output"]["message"]["content"]
        text = "".join(part.get("text", "") for part in output)
        usage = response["usage"]
        self._meter.record(purpose, model_id, usage["inputTokens"], usage["outputTokens"])
        return ChatResult(
            text=text,
            input_tokens=usage["inputTokens"],
            output_tokens=usage["outputTokens"],
        )
