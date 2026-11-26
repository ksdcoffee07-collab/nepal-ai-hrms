from django.core.exceptions import ValidationError
from django.test import TestCase

from employee.forms import EmployeeForm, EmployeePasswordResetForm
from horilla.testkit import make_company, make_employee
from horilla_auth.models import HorillaUser


class EmployeeInitialPasswordTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company("Initial Password Co")

    def _new_employee_form_data(self, email, password, confirmation=None):
        return {
            "employee_first_name": "New",
            "employee_last_name": "Employee",
            "email": email,
            "phone": "9999999999",
            "login_password": password,
            "login_password_confirmation": (
                password if confirmation is None else confirmation
            ),
        }

    def test_password_fields_are_limited_to_employee_creation(self):
        self.assertNotIn("login_password", EmployeeForm().fields)

        form = EmployeeForm(set_login_password=True)

        self.assertTrue(form.fields["login_password"].required)
        self.assertTrue(form.fields["login_password_confirmation"].required)
        self.assertEqual(
            form.fields["login_password"].widget.input_type,
            "password",
        )

    def test_employee_creation_uses_admin_supplied_password(self):
        password = "N3ptune_Arc9!Velvet"
        form = EmployeeForm(
            data=self._new_employee_form_data(
                "new.employee@test.horilla",
                password,
            ),
            set_login_password=True,
        )

        self.assertTrue(form.is_valid(), form.errors)
        employee = form.save(commit=False)
        employee.save(login_password=form.cleaned_data["login_password"])
        form.save_m2m()

        employee.employee_user_id.refresh_from_db()
        self.assertTrue(employee.employee_user_id.check_password(password))
        self.assertNotEqual(employee.employee_user_id.password, password)
        self.assertEqual(employee.employee_user_id.first_name, "New")
        self.assertEqual(employee.employee_user_id.last_name, "Employee")
        self.assertEqual(employee.employee_user_id.email, "new.employee@test.horilla")

    def test_employee_updates_sync_linked_user_name_and_email(self):
        user = HorillaUser.objects.create_user(
            username="existing-login",
            email="old@test.horilla",
            first_name="Old",
            last_name="Details",
            password="secret123",
        )
        employee = make_employee(
            company=self.company,
            email="profile@test.horilla",
            first_name="Initial",
            last_name="Profile",
            user=user,
        )

        user.refresh_from_db()
        self.assertEqual(user.email, employee.email)

        employee.employee_first_name = "Updated"
        employee.employee_last_name = "Employee"
        employee.email = "updated@test.horilla"
        employee.save()

        user.refresh_from_db()
        self.assertEqual(user.first_name, "Updated")
        self.assertEqual(user.last_name, "Employee")
        self.assertEqual(user.email, "updated@test.horilla")
        self.assertEqual(user.username, "existing-login")

    def test_employee_email_cannot_conflict_with_another_login_account(self):
        conflict = HorillaUser.objects.create_user(
            username="other-account",
            email="conflict@test.horilla",
            password="secret123",
        )
        employee = make_employee(
            company=self.company,
            email="profile@test.horilla",
            user=HorillaUser.objects.create_user(
                username="profile-account",
                email="old@test.horilla",
                password="secret123",
            ),
        )

        employee.email = conflict.email
        with self.assertRaises(ValidationError):
            employee.save()

        employee.refresh_from_db()
        self.assertEqual(employee.email, "profile@test.horilla")

    def test_password_confirmation_and_password_policy_are_enforced(self):
        mismatched_form = EmployeeForm(
            data=self._new_employee_form_data(
                "mismatch@test.horilla",
                "Solar!Crate_84",
                "different-password",
            ),
            set_login_password=True,
        )
        self.assertFalse(mismatched_form.is_valid())
        self.assertIn("login_password_confirmation", mismatched_form.errors)

        weak_form = EmployeeForm(
            data=self._new_employee_form_data(
                "weak@test.horilla",
                "short",
            ),
            set_login_password=True,
        )
        self.assertFalse(weak_form.is_valid())
        self.assertIn("login_password", weak_form.errors)

    def test_admin_reset_form_accepts_a_confirmed_valid_password(self):
        user = HorillaUser(
            username="existing.employee@test.horilla",
            email="existing.employee@test.horilla",
            first_name="Existing",
            last_name="Employee",
        )
        password = "N3ptune_Arc9!Velvet"
        form = EmployeePasswordResetForm(
            data={
                "password": password,
                "password_confirmation": password,
            },
            user=user,
        )

        self.assertTrue(form.is_valid(), form.errors)
