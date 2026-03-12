import json
from typing import override

from django.contrib.auth import get_user_model
from django.test import TestCase

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
