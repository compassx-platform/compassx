"""Core AI Gateway Service: Routing, Rate Limiting, Failover, and Telemetry."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from decimal import Decimal
from typing import Any, AsyncIterator
from sqlalchemy.orm import Session

from app.ai_gateway.models.inference_log import AIGatewayInferenceLog
from app.ai_gateway.models.provider import AIModelEndpoint, AIProvider
from app.ai_gateway.providers.base import ProviderCredentials
from app.ai_gateway.providers.factory import get_provider_adapter
from app.ai_gateway.schemas.chat import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
)
from app.ai_gateway.services.guardrails import AIGuardrails
from app.ai_gateway.services.rate_limiter import gateway_rate_limiter
from app.services.encryption import decrypt_field

logger = logging.getLogger(__name__)


class GatewayService:
    """Unified AI Gateway Engine."""

    @staticmethod
    def resolve_endpoint(
        db: Session,
        model_name_or_id: str | int,
        workspace_id: str | None = None,
    ) -> AIModelEndpoint | None:
        """Find an active AIModelEndpoint by name, alias, or ID."""
        query = db.query(AIModelEndpoint).filter(AIModelEndpoint.is_active == True)  # noqa: E712
        if workspace_id:
            query = query.filter((AIModelEndpoint.workspace_id == workspace_id) | (AIModelEndpoint.workspace_id.is_(None)))

        if isinstance(model_name_or_id, int) or (isinstance(model_name_or_id, str) and model_name_or_id.isdigit()):
            endpoint = query.filter(AIModelEndpoint.id == int(model_name_or_id)).first()
            if endpoint:
                return endpoint

        # Match by name
        endpoint = query.filter(AIModelEndpoint.name == str(model_name_or_id)).first()
        if endpoint:
            return endpoint

        # Match by upstream_model_name
        endpoint = query.filter(AIModelEndpoint.upstream_model_name == str(model_name_or_id)).first()
        if endpoint:
            return endpoint

        # Fallback to default endpoint if requested model is "default" or not found
        if model_name_or_id in ("default", "default-chat", None):
            return query.filter(AIModelEndpoint.is_default == True).first() or query.first()  # noqa: E712

        return None

    @staticmethod
    def get_provider_credentials(provider: AIProvider) -> ProviderCredentials:
        """Extract and decrypt credentials for a provider."""
        api_key = None
        if provider.api_key_enc:
            try:
                api_key = decrypt_field(provider.api_key_enc)
            except Exception as e:
                logger.warning("Failed to decrypt API key for provider %s: %s", provider.name, e)

        return ProviderCredentials(
            api_key=api_key,
            base_url=provider.base_url,
            config=provider.config or {},
        )

    @staticmethod
    async def chat_stream(
        db: Session,
        request: ChatCompletionRequest,
        workspace_id: str | None = None,
        user_id: str | None = None,
        caller_type: str = "direct_api",
        caller_id: str | None = None,
    ) -> AsyncIterator[ChatCompletionChunk]:
        """Stream chat completions through the gateway with rate limiting, guardrails, and failover."""
        start_time = time.time()
        primary_endpoint = GatewayService.resolve_endpoint(db, request.model, workspace_id)
        if not primary_endpoint:
            raise ValueError(f"No active AI Model Endpoint found for model '{request.model}'")

        # Rate Limit Check
        rate_key = f"{workspace_id or 'global'}:{primary_endpoint.id}"
        gateway_rate_limiter.check_and_record(
            rate_key,
            limit_rpm=primary_endpoint.rate_limit_rpm,
            limit_tpm=primary_endpoint.rate_limit_tpm,
            estimated_tokens=500,
        )

        # Apply PII Guardrails
        if primary_endpoint.guardrail_config:
            messages_dict = [m.model_dump(exclude_none=True) for m in request.messages]
            sanitized = AIGuardrails.apply_guardrails_to_messages(messages_dict, primary_endpoint.guardrail_config)
            # update request messages
            for i, s_msg in enumerate(sanitized):
                if i < len(request.messages) and "content" in s_msg:
                    request.messages[i].content = s_msg["content"]

        # Build execution chain: [primary_endpoint] + fallback endpoints
        candidate_endpoints = [primary_endpoint]
        if primary_endpoint.fallback_endpoint_ids:
            for fb_id in primary_endpoint.fallback_endpoint_ids:
                fb_ep = db.query(AIModelEndpoint).filter(AIModelEndpoint.id == fb_id, AIModelEndpoint.is_active == True).first()  # noqa: E712
                if fb_ep:
                    candidate_endpoints.append(fb_ep)

        last_error = None
        executed_endpoint = None
        accumulated_text = ""
        accumulated_tools = []
        input_tokens = 0
        output_tokens = 0
        finish_reason = None

        for endpoint in candidate_endpoints:
            provider = endpoint.provider
            if not provider or not provider.is_active:
                continue

            creds = GatewayService.get_provider_credentials(provider)
            adapter = get_provider_adapter(provider.provider_type)

            try:
                executed_endpoint = endpoint
                stream_iter = adapter.chat_stream(request, creds, endpoint.upstream_model_name)
                async for chunk in stream_iter:
                    # Accumulate for telemetry
                    if chunk.choices and chunk.choices[0].delta:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            accumulated_text += delta.content
                        if delta.tool_calls:
                            accumulated_tools.extend(delta.tool_calls)
                        if chunk.choices[0].finish_reason:
                            finish_reason = chunk.choices[0].finish_reason
                    if chunk.usage:
                        input_tokens = chunk.usage.prompt_tokens or input_tokens
                        output_tokens = chunk.usage.completion_tokens or output_tokens
                    yield chunk

                last_error = None
                break  # Successful stream completion
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Endpoint %s (provider %s) failed during streaming: %s. Attempting fallback...",
                    endpoint.name,
                    provider.name,
                    exc,
                )
                continue

        latency_ms = int((time.time() - start_time) * 1000)

        # Telemetry / Inference Logging
        if executed_endpoint:
            status_code = 500 if last_error else 200
            err_msg = str(last_error) if last_error else None

            # Calculate cost
            total_cost = Decimal(0)
            if executed_endpoint.input_cost_per_1k_tokens and input_tokens:
                total_cost += (Decimal(input_tokens) / Decimal(1000)) * executed_endpoint.input_cost_per_1k_tokens
            if executed_endpoint.output_cost_per_1k_tokens and output_tokens:
                total_cost += (Decimal(output_tokens) / Decimal(1000)) * executed_endpoint.output_cost_per_1k_tokens

            try:
                from app.database import SystemSessionLocal
                sys_db = SystemSessionLocal()
                try:
                    log_entry = AIGatewayInferenceLog(
                        workspace_id=workspace_id,
                        user_id=user_id,
                        caller_type=caller_type,
                        caller_id=caller_id,
                        endpoint_id=executed_endpoint.id,
                        endpoint_name=executed_endpoint.name,
                        provider_type=executed_endpoint.provider.provider_type.value,
                        upstream_model_name=executed_endpoint.upstream_model_name,
                        request_messages=[m.model_dump(exclude_none=True) for m in request.messages],
                        tools_passed=[t.model_dump(exclude_none=True) for t in request.tools] if request.tools else None,
                        response_text=accumulated_text or None,
                        response_tool_calls=accumulated_tools or None,
                        finish_reason=finish_reason,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_cost=total_cost,
                        latency_ms=latency_ms,
                        status_code=status_code,
                        error_message=err_msg,
                    )
                    sys_db.add(log_entry)
                    sys_db.commit()
                finally:
                    sys_db.close()
            except Exception as log_err:
                logger.warning("Could not record AI Gateway inference log: %s", log_err)

        if last_error:
            raise last_error

    @staticmethod
    async def chat_complete(
        db: Session,
        request: ChatCompletionRequest,
        workspace_id: str | None = None,
        user_id: str | None = None,
        caller_type: str = "direct_api",
        caller_id: str | None = None,
    ) -> ChatCompletionResponse:
        """Non-streaming chat completion through the gateway with failover and logging."""
        start_time = time.time()
        primary_endpoint = GatewayService.resolve_endpoint(db, request.model, workspace_id)
        if not primary_endpoint:
            raise ValueError(f"No active AI Model Endpoint found for model '{request.model}'")

        # Rate Limit Check
        rate_key = f"{workspace_id or 'global'}:{primary_endpoint.id}"
        gateway_rate_limiter.check_and_record(
            rate_key,
            limit_rpm=primary_endpoint.rate_limit_rpm,
            limit_tpm=primary_endpoint.rate_limit_tpm,
            estimated_tokens=500,
        )

        # Apply PII Guardrails
        if primary_endpoint.guardrail_config:
            messages_dict = [m.model_dump(exclude_none=True) for m in request.messages]
            sanitized = AIGuardrails.apply_guardrails_to_messages(messages_dict, primary_endpoint.guardrail_config)
            for i, s_msg in enumerate(sanitized):
                if i < len(request.messages) and "content" in s_msg:
                    request.messages[i].content = s_msg["content"]

        candidate_endpoints = [primary_endpoint]
        if primary_endpoint.fallback_endpoint_ids:
            for fb_id in primary_endpoint.fallback_endpoint_ids:
                fb_ep = db.query(AIModelEndpoint).filter(AIModelEndpoint.id == fb_id, AIModelEndpoint.is_active == True).first()  # noqa: E712
                if fb_ep:
                    candidate_endpoints.append(fb_ep)

        last_error = None
        executed_endpoint = None
        response_obj: ChatCompletionResponse | None = None

        for endpoint in candidate_endpoints:
            provider = endpoint.provider
            if not provider or not provider.is_active:
                continue

            creds = GatewayService.get_provider_credentials(provider)
            adapter = get_provider_adapter(provider.provider_type)

            try:
                executed_endpoint = endpoint
                response_obj = await adapter.chat_complete(request, creds, endpoint.upstream_model_name)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Endpoint %s (provider %s) failed: %s. Attempting fallback...",
                    endpoint.name,
                    provider.name,
                    exc,
                )
                continue

        latency_ms = int((time.time() - start_time) * 1000)

        # Log telemetry
        if executed_endpoint and response_obj:
            input_tokens = response_obj.usage.prompt_tokens if response_obj.usage else 0
            output_tokens = response_obj.usage.completion_tokens if response_obj.usage else 0

            total_cost = Decimal(0)
            if executed_endpoint.input_cost_per_1k_tokens and input_tokens:
                total_cost += (Decimal(input_tokens) / Decimal(1000)) * executed_endpoint.input_cost_per_1k_tokens
            if executed_endpoint.output_cost_per_1k_tokens and output_tokens:
                total_cost += (Decimal(output_tokens) / Decimal(1000)) * executed_endpoint.output_cost_per_1k_tokens

            try:
                from app.database import SystemSessionLocal
                sys_db = SystemSessionLocal()
                try:
                    choice = response_obj.choices[0] if response_obj.choices else None
                    log_entry = AIGatewayInferenceLog(
                        workspace_id=workspace_id,
                        user_id=user_id,
                        caller_type=caller_type,
                        caller_id=caller_id,
                        endpoint_id=executed_endpoint.id,
                        endpoint_name=executed_endpoint.name,
                        provider_type=executed_endpoint.provider.provider_type.value,
                        upstream_model_name=executed_endpoint.upstream_model_name,
                        request_messages=[m.model_dump(exclude_none=True) for m in request.messages],
                        tools_passed=[t.model_dump(exclude_none=True) for t in request.tools] if request.tools else None,
                        response_text=choice.message.content if choice and choice.message else None,
                        response_tool_calls=[tc.model_dump(exclude_none=True) for tc in choice.message.tool_calls] if choice and choice.message and choice.message.tool_calls else None,
                        finish_reason=choice.finish_reason if choice else "stop",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_cost=total_cost,
                        latency_ms=latency_ms,
                        status_code=200,
                    )
                    sys_db.add(log_entry)
                    sys_db.commit()
                finally:
                    sys_db.close()
            except Exception as log_err:
                logger.warning("Could not record AI Gateway inference log: %s", log_err)

        if last_error:
            raise last_error

        return response_obj

    @staticmethod
    async def embed(
        db: Session,
        texts: list[str],
        model_name_or_id: str | int | None = None,
        workspace_id: str | None = None,
    ) -> list[list[float]]:
        """Generate vector embeddings through the configured embedding endpoint."""
        query = db.query(AIModelEndpoint).filter(
            AIModelEndpoint.is_active == True,  # noqa: E712
            AIModelEndpoint.use_for_embedding == True,  # noqa: E712
        )
        if workspace_id:
            query = query.filter((AIModelEndpoint.workspace_id == workspace_id) | (AIModelEndpoint.workspace_id.is_(None)))

        if model_name_or_id:
            endpoint = GatewayService.resolve_endpoint(db, model_name_or_id, workspace_id)
        else:
            endpoint = query.first()

        if not endpoint:
            # Fallback to any active endpoint if no explicit embedding flag set
            endpoint = db.query(AIModelEndpoint).filter(AIModelEndpoint.is_active == True).first()  # noqa: E712

        if not endpoint or not endpoint.provider:
            raise ValueError("No active embedding model endpoint configured in AI Gateway.")

        creds = GatewayService.get_provider_credentials(endpoint.provider)
        adapter = get_provider_adapter(endpoint.provider.provider_type)
        return await adapter.embed(texts, creds, endpoint.upstream_model_name)
