from django.conf import settings
from django.db import migrations


BATCH_SIZE = 500


def synchronize_employee_users(apps, schema_editor):
    Employee = apps.get_model("employee", "Employee")
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)
    database = schema_editor.connection.alias
    employees = (
        Employee.objects.using(database)
        .exclude(employee_user_id__isnull=True)
        .only(
            "id",
            "employee_user_id",
            "employee_first_name",
            "employee_last_name",
            "email",
        )
    )

    conflicting_employees = []
    for employee in employees.iterator(chunk_size=BATCH_SIZE):
        conflict = (
            User.objects.using(database)
            .filter(email__iexact=employee.email)
            .exclude(pk=employee.employee_user_id_id)
            .exists()
        )
        if conflict:
            conflicting_employees.append(employee.pk)

    if conflicting_employees:
        sample_ids = ", ".join(str(pk) for pk in conflicting_employees[:20])
        raise RuntimeError(
            "Cannot synchronize employee login details because Employee records "
            f"{sample_ids} have emails used by another login account. Resolve "
            "the duplicate account emails and rerun migrations."
        )

    batch = []
    for employee in employees.iterator(chunk_size=BATCH_SIZE):
        batch.append(
            User(
                pk=employee.employee_user_id_id,
                first_name=employee.employee_first_name,
                last_name=employee.employee_last_name or "",
                email=employee.email,
            )
        )
        if len(batch) == BATCH_SIZE:
            User.objects.using(database).bulk_update(
                batch, ["first_name", "last_name", "email"], batch_size=BATCH_SIZE
            )
            batch.clear()

    if batch:
        User.objects.using(database).bulk_update(
            batch, ["first_name", "last_name", "email"], batch_size=BATCH_SIZE
        )


class Migration(migrations.Migration):
    dependencies = [
        ("employee", "0009_alter_actiontype_is_active_and_more"),
        ("horilla_auth", "0002_alter_horillauser_first_name_and_more"),
    ]

    operations = [
        migrations.RunPython(
            synchronize_employee_users,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
