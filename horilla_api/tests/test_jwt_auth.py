"""Horilla API JWT login and auth-gate smoke tests."""

import base64

from django.test import Client, TestCase
from rest_framework.test import APIClient

from horilla.testkit import make_company, make_employee, make_user


class LoginAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = make_company("API Co")
        self.password = "secret123"
        self.user = make_user("api_login", password=self.password)
        self.employee = make_employee(
            company=self.company,
            email="api_login@test.horilla",
            user=self.user,
        )

    def test_login_returns_access_token(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": "api_login", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertTrue(response.data["access"])
        self.assertEqual(response.data["employee"]["id"], self.employee.pk)
        self.assertEqual(response.data["employee"]["full_name"], "Test Employee")
        self.assertEqual(response.data["employee"]["email"], self.employee.email)

    def test_login_accepts_email_as_identifier(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": self.user.email.upper(), "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["employee"]["id"], self.employee.pk)

    def test_login_accepts_email_field_as_identifier(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["employee"]["id"], self.employee.pk)

    def test_account_email_takes_precedence_over_another_users_username(self):
        shadow_user = make_user(
            self.user.email,
            password=self.password,
            email="shadow@test.horilla",
        )
        shadow_employee = make_employee(
            company=self.company,
            email="shadow-employee@test.horilla",
            first_name="Shadow",
            last_name="Account",
            user=shadow_user,
        )

        response = self.client.post(
            "/api/auth/login/",
            {"username": self.user.email, "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["employee"]["id"], self.employee.pk)
        self.assertNotEqual(response.data["employee"]["id"], shadow_employee.pk)
        self.assertEqual(response.data["employee"]["email"], self.employee.email)

    def test_employee_email_takes_precedence_over_another_users_username(self):
        employee_email = "profile_email@test.horilla"
        type(self.employee).objects.filter(pk=self.employee.pk).update(
            email=employee_email
        )
        shadow_user = make_user(
            employee_email,
            password=self.password,
            email="shadow@test.horilla",
        )
        make_employee(
            company=self.company,
            email="shadow-employee@test.horilla",
            first_name="Shadow",
            last_name="Account",
            user=shadow_user,
        )

        response = self.client.post(
            "/api/auth/login/",
            {"username": employee_email, "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["employee"]["id"], self.employee.pk)
        self.assertEqual(response.data["employee"]["email"], employee_email)

    def test_login_rejects_conflicting_username_and_email(self):
        response = self.client.post(
            "/api/auth/login/",
            {
                "username": self.user.username,
                "email": "someone-else@test.horilla",
                "password": self.password,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_login_accepts_employee_email_when_account_email_differs(self):
        employee_email = "profile_email@test.horilla"
        type(self.employee).objects.filter(pk=self.employee.pk).update(
            email=employee_email
        )
        response = self.client.post(
            "/api/auth/login/",
            {"username": employee_email, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["employee"]["id"], self.employee.pk)

    def test_login_rejects_an_email_shared_by_multiple_users(self):
        make_user("another_api_login", password=self.password, email=self.user.email)
        response = self.client.post(
            "/api/auth/login/",
            {"username": self.user.email, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, 401)


class JWTProtectedEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        company = make_company("API Gate")
        self.password = "secret123"
        self.user = make_user("api_gate", password=self.password)
        make_employee(
            company=company,
            email="api_gate@test.horilla",
            user=self.user,
        )

    def test_unauthenticated_gets_401(self):
        response = self.client.get("/api/employee/employee-type/")
        self.assertEqual(response.status_code, 401)

    def test_jwt_allows_access(self):
        login = self.client.post(
            "/api/auth/login/",
            {"username": "api_gate", "password": self.password},
            format="json",
        )
        token = login.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get("/api/employee/employee-type/")
        self.assertEqual(response.status_code, 200)


class RejectBasicAuthTests(TestCase):
    def test_basic_auth_does_not_authenticate_api(self):
        """Basic credentials must not unlock JWT-only endpoints."""
        client = Client()
        creds = base64.b64encode(b"user:pass").decode("ascii")
        response = client.get(
            "/api/employee/employee-type/",
            HTTP_AUTHORIZATION=f"Basic {creds}",
        )
        self.assertEqual(response.status_code, 401)


class PasswordResetAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "secret123"
        self.user = make_user("api_reset", password=self.password)

    def test_unauthenticated_reset_gets_401(self):
        response = self.client.post(
            "/api/auth/reset-password/",
            {
                "old_password": self.password,
                "new_password": "newsecret1",
                "confirm_password": "newsecret1",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_wrong_old_password_gets_400(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/auth/reset-password/",
            {
                "old_password": "wrong-old",
                "new_password": "newsecret1",
                "confirm_password": "newsecret1",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("old_password", response.data)

    def test_successful_password_reset(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/auth/reset-password/",
            {
                "old_password": self.password,
                "new_password": "newsecret99",
                "confirm_password": "newsecret99",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newsecret99"))
