"""Restrict the operator dashboard, including static files and API documentation."""
import base64
import hmac

from starlette.requests import Request
from starlette.responses import PlainTextResponse

LOOPBACK = {"127.0.0.1", "::1", "localhost"}


class DashboardAccess:
    def __init__(self, app, password):
        self.app = app
        self.expected_auth = (b"Basic " + base64.b64encode(("admin:" + password).encode())) if password else None

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope)
            if self.expected_auth:
                authorization = request.headers.get("authorization", "").encode("latin1")
                if not hmac.compare_digest(authorization, self.expected_auth):
                    response = PlainTextResponse("Operator login required", 401,
                                                 headers={"WWW-Authenticate": 'Basic realm="Dashboard", charset="UTF-8"'})
                    return await response(scope, receive, send)
            elif not (request.client and request.client.host in LOOPBACK and request.url.hostname in LOOPBACK):
                return await PlainTextResponse("Local access only", 403)(scope, receive, send)

            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                origin = request.headers.get("origin")
                same_origin = f"{request.url.scheme}://{request.url.netloc}"
                if (origin and origin != same_origin) or request.headers.get("sec-fetch-site") == "cross-site":
                    return await PlainTextResponse("Cross-site request denied", 403)(scope, receive, send)
                if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
                    return await PlainTextResponse("Expected application/json", 415)(scope, receive, send)
        await self.app(scope, receive, send)
