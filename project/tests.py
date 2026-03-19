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
        self.assertIn("errors", data)

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
