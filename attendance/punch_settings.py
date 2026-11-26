def get_attendance_settings_for_request(request):
    from attendance.models import AttendanceGeneralSetting
    from base.models import Company

    selected_company = request.session.get("selected_company")
    if selected_company == "all":
        company = None
    elif selected_company:
        company = Company.objects.filter(id=selected_company).first()
        if company is None:
            return None, None
    else:
        employee = getattr(getattr(request, "user", None), "employee_get", None)
        if employee is None:
            return None, None
        company = employee.get_company()
        if company is None:
            return None, None

    attendance_settings = AttendanceGeneralSetting.objects.filter(
        company_id=company
    ).first()
    return company, attendance_settings
