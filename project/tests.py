import json
from typing import override

from django.contrib.auth import get_user_model
from django.test import TestCase
from ninja_jwt.tokens import AccessToken

User = get_user_model()


class JWTTokenEndpointTest(TestCase):
    @override
    def setUp(self) -> None:
        _ = User.objects.create_user(username="tokenuser", password="pass123!")

    def test_token_pair_returns_access_and_refresh(self) -> None:
        response = self.client.post(
            "/api/token/pair",
            data=json.dumps({"username": "tokenuser", "password": "pass123!"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access", data)
        self.assertIn("refresh", data)

    def test_token_pair_rejects_wrong_credentials(self) -> None:
        response = self.client.post(
            "/api/token/pair",
            data=json.dumps({"username": "tokenuser", "password": "wrong"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)


class FrameworkErrorTagTest(TestCase):
    """Verify that framework exceptions produce tagged JSON responses."""

    def test_validation_error_has_tag(self) -> None:
        """Invalid query param triggers ninja ValidationError → tagged 422."""
        user = User.objects.create_user(username="fwuser", password="pass123!")
        token = f"Bearer {AccessToken.for_user(user)}"
        response = self.client.get("/api/orders/?status=bogus", HTTP_AUTHORIZATION=token)
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertEqual(data["tag"], "ValidationError")
        self.assertIsInstance(data["detail"], list)

    def test_authentication_error_has_tag(self) -> None:
        """Missing auth on a protected endpoint → tagged 401."""
        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertEqual(data["tag"], "AuthenticationError")

    def test_not_found_error_has_tag(self) -> None:
        """Request to a non-existent URL → tagged 404."""
        response = self.client.get("/api/nonexistent/")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["tag"], "NotFoundError")

    def test_domain_error_has_tag(self) -> None:
        """AppException → tagged 400."""
        user = User.objects.create_user(username="domuser", password="pass123!")
        token = f"Bearer {AccessToken.for_user(user)}"
        response = self.client.get("/api/orders/99999/", HTTP_AUTHORIZATION=token)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["tag"], "OrderNotFoundError")


class OpenAPISchemaInjectionTest(TestCase):
    """Verify that framework error schemas are injected into every endpoint."""

    def test_endpoint_has_validation_error_schema(self) -> None:
        """Every endpoint should have a 422 response with ValidationError schema."""
        response = self.client.get("/api/openapi.json")
        schema = response.json()
        # Check a specific endpoint — get_order
        get_order_responses = schema["paths"]["/api/orders/{order_id}/"]["get"]["responses"]
        self.assertIn("422", get_order_responses)
        content = get_order_responses["422"]["content"]["application/json"]["schema"]
        self.assertIn("properties", content)
        self.assertEqual(content["properties"]["tag"]["const"], "ValidationError")

    def test_authenticated_endpoint_has_auth_error_schema(self) -> None:
        """Endpoints with auth should have 401 and 403 responses."""
        response = self.client.get("/api/openapi.json")
        schema = response.json()
        get_order_responses = schema["paths"]["/api/orders/{order_id}/"]["get"]["responses"]
        self.assertIn("401", get_order_responses)
        self.assertIn("403", get_order_responses)

    def test_unauthenticated_endpoint_has_no_auth_error_schema(self) -> None:
        """Endpoints without auth should NOT have 401/403 responses."""
        response = self.client.get("/api/openapi.json")
        schema = response.json()
        get_posts_responses = schema["paths"]["/api/blog/posts/"]["get"]["responses"]
        self.assertNotIn("401", get_posts_responses)
        self.assertNotIn("403", get_posts_responses)

    def test_validation_error_item_schema_includes_ctx(self) -> None:
        """ValidationError item schema should include optional ctx field."""
        response = self.client.get("/api/openapi.json")
        schema = response.json()
        get_order_responses = schema["paths"]["/api/orders/{order_id}/"]["get"]["responses"]
        content = get_order_responses["422"]["content"]["application/json"]["schema"]
        error_items = content["properties"]["detail"]["items"]
        self.assertIn("ctx", error_items["properties"])
        self.assertNotIn("ctx", error_items["required"])

    def test_every_endpoint_has_internal_error_schema(self) -> None:
        """Every endpoint should have a 500 response with InternalError schema."""
        response = self.client.get("/api/openapi.json")
        schema = response.json()
        for path, methods in schema["paths"].items():
            for method, details in methods.items():
                if method in ("get", "post", "put", "patch", "delete"):
                    self.assertIn(
                        "500",
                        details["responses"],
                        f"{method.upper()} {path} missing 500 response",
                    )


class OnExceptionTagInjectionTest(TestCase):
    """Verify that on_exception injects tags into framework error responses."""

    def test_http_error_gets_status_code_in_body(self) -> None:
        """HttpError subclass responses should include status_code in the body."""
        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertIn("status_code", data)
        self.assertEqual(data["status_code"], 401)
