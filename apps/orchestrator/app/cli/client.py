"""HTTP-only boundary used by the terminal client."""

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx
import typer
from rich.console import Console
from rich.panel import Panel


class CliConfigError(ValueError):
    pass


class ApiError(RuntimeError):
    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        code: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.code = code
        self.trace_id = trace_id


class ApiConnectionError(RuntimeError):
    pass


class ApiClient:
    """Small synchronous client; orchestration behavior remains in FastAPI."""

    def __init__(
        self,
        base_url: str,
        *,
        reviewer_token: str | None = None,
        reviewer_id: str = "local-cli",
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CliConfigError("The orchestrator base URL must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password:
            raise CliConfigError("Credentials must not be embedded in the orchestrator URL")
        self.base_url = base_url.rstrip("/")
        self.reviewer_token = reviewer_token
        self.reviewer_id = reviewer_id.strip() or "local-cli"
        self._http = httpx.Client(timeout=timeout_seconds, transport=transport)

    def request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        reviewer: bool = False,
    ) -> Any:
        response = self._request(
            method,
            path,
            json_body=json_body,
            params=params,
            reviewer=reviewer,
        )
        try:
            return response.json()
        except ValueError as error:
            raise ApiError(
                response.status_code,
                "The orchestrator returned invalid JSON",
                trace_id=response.headers.get("X-Trace-Id"),
            ) from error

    def request_text(self, method: str, path: str, *, params: dict[str, Any] | None = None) -> str:
        return self._request(method, path, params=params).text

    def close(self) -> None:
        self._http.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        reviewer: bool = False,
    ) -> httpx.Response:
        headers = {"Accept": "application/json"}
        if reviewer:
            if not self.reviewer_token:
                raise CliConfigError(
                    "ORCHESTRATOR_LOCAL_REVIEWER_TOKEN is required for this command"
                )
            headers.update(
                {
                    "Authorization": f"Bearer {self.reviewer_token}",
                    "X-Reviewer-Id": self.reviewer_id,
                }
            )
        try:
            response = self._http.request(
                method,
                f"{self.base_url}{path}",
                json=json_body,
                params=params,
                headers=headers,
            )
        except httpx.RequestError as error:
            raise ApiConnectionError(f"Cannot reach the orchestrator at {self.base_url}") from error
        if response.is_error:
            raise self._api_error(response)
        return response

    @staticmethod
    def _api_error(response: httpx.Response) -> ApiError:
        code = None
        message = f"The orchestrator returned HTTP {response.status_code}"
        trace_id = response.headers.get("X-Trace-Id")
        try:
            body = response.json()
            trace_id = body.get("traceId", trace_id) if isinstance(body, dict) else trace_id
            error = body.get("error") if isinstance(body, dict) else None
            if isinstance(error, dict):
                code = error.get("code")
                message = error.get("message") or message
            elif isinstance(body, dict) and isinstance(body.get("detail"), str):
                message = body["detail"]
        except ValueError:
            pass
        return ApiError(response.status_code, message, code=code, trace_id=trace_id)


@dataclass
class CliRuntime:
    client: ApiClient
    console: Console
    json_output: bool = False


def make_api_client(base_url: str) -> ApiClient:
    return ApiClient(
        base_url,
        reviewer_token=os.getenv("ORCHESTRATOR_LOCAL_REVIEWER_TOKEN"),
        reviewer_id=os.getenv("AGENTIC_REVIEWER_ID", "local-cli"),
    )


def runtime_from(context: typer.Context) -> CliRuntime:
    if not isinstance(context.obj, CliRuntime):
        raise RuntimeError("CLI runtime was not initialized")
    return context.obj


def api_json(
    runtime: CliRuntime,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    reviewer: bool = False,
) -> Any:
    try:
        return runtime.client.request_json(
            method,
            path,
            json_body=json_body,
            params=params,
            reviewer=reviewer,
        )
    except (ApiError, ApiConnectionError, CliConfigError) as error:
        _exit_for_error(runtime.console, error)


def api_text(
    runtime: CliRuntime,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
) -> str:
    try:
        return runtime.client.request_text(method, path, params=params)
    except (ApiError, ApiConnectionError, CliConfigError) as error:
        _exit_for_error(runtime.console, error)


def fail(console: Console, message: str, *, code: int = 2) -> None:
    console.print(Panel(message, title="[bold red]Error[/bold red]", border_style="red"))
    raise typer.Exit(code)


def _exit_for_error(console: Console, error: Exception) -> None:
    if isinstance(error, ApiError):
        details = [error.message]
        if error.code:
            details.append(f"Code: {error.code}")
        if error.trace_id:
            details.append(f"Trace: {error.trace_id}")
        fail(console, "\n".join(details), code=4 if error.status_code < 500 else 5)
    if isinstance(error, ApiConnectionError):
        fail(console, str(error), code=3)
    fail(console, str(error), code=2)
