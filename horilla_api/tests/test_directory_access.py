"""Mobile directory access is self/manager scoped unless explicitly granted.

An unconfigured web accessibility feature defaults to open. The API does not:
only an enabled, employee-specific accessibility grant or ``view_employee``
permission may expose the full directory.
"""

from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIClient

from accessibility.models import DefaultAccessibility
from horilla.horilla_middlewares import set_selected_company
from horilla.testkit import make_company, make_employee, make_user

LIST_URL = "/api/v1/employee/list/employees/"


class DirectoryAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        set_selected_company(None)
        self.company = make_company("Directory Co")

        self.user = make_user("dir_user")
        self.employee = make_employee(
            company=self.company,
            email="dir@test.horilla",
            first_name="Dana",
            user=self.user,
        )
        for i in range(3):
            make_employee(
                company=self.company,
                email=f"colleague{i}@test.horilla",
                first_name=f"Colleague{i}",
            )
        self.client.force_authenticate(user=self.user)

    def test_unconfigured_feature_limits_directory_to_self(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.employee.id)

    def test_explicit_accessibility_grant_can_show_the_directory(self):
        access = DefaultAccessibility.objects.create(
            feature="employee_view", is_enabled=True, exclude_all=False, filter="{}"
        )
        access.employees.add(self.employee)

        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertGreater(response.data["count"], 1)

    def test_disabled_feature_does_not_grant_the_directory(self):
        DefaultAccessibility.objects.create(
            feature="employee_view", is_enabled=False, exclude_all=False, filter="{}"
        )
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["count"], 1)

    def test_excluded_feature_falls_back_to_self_only(self):
        DefaultAccessibility.objects.create(
            feature="employee_view", is_enabled=True, exclude_all=True, filter="{}"
        )
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.employee.id)

    def test_perm_holder_is_unaffected_by_exclusion(self):
        DefaultAccessibility.objects.create(
            feature="employee_view", is_enabled=True, exclude_all=True, filter="{}"
        )
        self.user.user_permissions.add(Permission.objects.get(codename="view_employee"))
        # Re-authenticate so the permission cache is rebuilt.
        client = APIClient()
        client.force_authenticate(user=type(self.user).objects.get(pk=self.user.pk))
        response = client.get(LIST_URL)
        self.assertGreater(response.data["count"], 1)

    def test_manager_still_sees_subordinates_when_excluded(self):
        DefaultAccessibility.objects.create(
            feature="employee_view", is_enabled=True, exclude_all=True, filter="{}"
        )
        report = make_employee(
            company=self.company,
            email="dir_report@test.horilla",
            first_name="Rudi",
        )
        report.employee_work_info.reporting_manager_id = self.employee
        report.employee_work_info.save()

        response = self.client.get(LIST_URL)
        ids = {row["id"] for row in response.data["results"]}
        self.assertIn(report.id, ids)

    def test_payload_exposes_only_directory_fields(self):
        """Widening the rows must not widen the columns."""
        row = self.client.get(LIST_URL).data["results"][0]
        for leaked in ("dob", "address", "phone", "marital_status", "children"):
            self.assertNotIn(leaked, row, f"{leaked} must not appear in the directory")
