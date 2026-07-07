from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
import datetime

from .models import UserProfile, LeaveType, LeaveBalance, LeaveRequest


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def get_role(user):
    try:
        return user.profile.role
    except Exception:
        return 'employee'


def send_notification(subject, message, recipient_email):
    """Send email notification — safe, never crashes the app on failure."""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=True,
        )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────────────────
def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_active:
            login(request, user)
            return redirect('dashboard_redirect')
        else:
            messages.error(request, 'Invalid username or password. Please try again.')

    return render(request, 'leave_app/login.html')


def user_logout(request):
    logout(request)
    return redirect('login')


@login_required(login_url='/login/')
def dashboard_redirect(request):
    role = get_role(request.user)
    if role == 'boss':
        return redirect('boss_dashboard')
    elif role == 'hr':
        return redirect('hr_dashboard')
    elif role == 'manager':
        return redirect('manager_dashboard')
    else:
        return redirect('employee_dashboard')


# ─────────────────────────────────────────────────────────────────────────────
# EMPLOYEE VIEWS
# ─────────────────────────────────────────────────────────────────────────────
@login_required(login_url='/login/')
def employee_dashboard(request):
    if get_role(request.user) not in ('employee',):
        return redirect('dashboard_redirect')

    year = datetime.date.today().year
    my_requests = LeaveRequest.objects.filter(employee=request.user)
    balances    = LeaveBalance.objects.filter(
        employee=request.user, year=year
    ).select_related('leave_type')

    stats = {
        'pending':  my_requests.filter(status='pending').count(),
        'approved': my_requests.filter(status='approved').count(),
        'rejected': my_requests.filter(status='rejected').count(),
        'total':    my_requests.count(),
    }

    return render(request, 'leave_app/employee/dashboard.html', {
        'requests': my_requests[:10],
        'balances': balances,
        'stats':    stats,
    })


@login_required(login_url='/login/')
def apply_leave(request):
    if get_role(request.user) not in ('employee',):
        return redirect('dashboard_redirect')

    year        = datetime.date.today().year
    leave_types = LeaveType.objects.all()
    balances    = {
        b.leave_type_id: b
        for b in LeaveBalance.objects.filter(employee=request.user, year=year)
    }

    if request.method == 'POST':
        lt_id      = request.POST.get('leave_type')
        start_str  = request.POST.get('start_date')
        end_str    = request.POST.get('end_date')
        reason     = request.POST.get('reason', '').strip()

        # Validate
        errors = []
        if not lt_id:
            errors.append('Please select a leave type.')
        if not reason:
            errors.append('Please provide a reason.')

        try:
            start = datetime.date.fromisoformat(start_str)
            end   = datetime.date.fromisoformat(end_str)
            if end < start:
                errors.append('End date cannot be before start date.')
            if start < datetime.date.today():
                errors.append('Start date cannot be in the past.')
        except (ValueError, TypeError):
            errors.append('Invalid dates selected.')
            start = end = None

        if not errors and start and end:
            leave_type = get_object_or_404(LeaveType, id=lt_id)
            days_requested = (end - start).days + 1
            balance = balances.get(leave_type.id)

            if not balance:
                errors.append(f'No {leave_type.name} balance assigned. Contact HR.')
            elif days_requested > balance.remaining_days:
                errors.append(
                    f'Insufficient balance. You have {balance.remaining_days} '
                    f'{leave_type.name} day(s) remaining.'
                )

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            req = LeaveRequest.objects.create(
                employee=request.user,
                leave_type=leave_type,
                start_date=start,
                end_date=end,
                reason=reason,
            )
            # Notify manager
            try:
                mgr = request.user.profile.manager
                if mgr:
                    send_notification(
                        subject=f"Leave Request from {request.user.get_full_name() or request.user.username}",
                        message=(
                            f"{request.user.get_full_name() or request.user.username} has applied for "
                            f"{leave_type.name} from {start} to {end} ({days_requested} day(s)).\n\n"
                            f"Reason: {reason}\n\nPlease log in to Empleave to review."
                        ),
                        recipient_email=mgr.email,
                    )
            except Exception:
                pass

            messages.success(request, f'Leave request submitted for {days_requested} day(s).')
            return redirect('employee_dashboard')

    return render(request, 'leave_app/employee/apply_leave.html', {
        'leave_types': leave_types,
        'balances':    balances,
    })


@login_required(login_url='/login/')
def my_leaves(request):
    if get_role(request.user) not in ('employee',):
        return redirect('dashboard_redirect')

    all_requests = LeaveRequest.objects.filter(employee=request.user)
    return render(request, 'leave_app/employee/my_leaves.html', {'requests': all_requests})


# ─────────────────────────────────────────────────────────────────────────────
# MANAGER VIEWS
# ─────────────────────────────────────────────────────────────────────────────
@login_required(login_url='/login/')
def manager_dashboard(request):
    if get_role(request.user) != 'manager':
        return redirect('dashboard_redirect')

    team_requests = LeaveRequest.objects.filter(
        employee__profile__manager=request.user
    ).select_related('employee', 'leave_type', 'employee__profile')

    stats = {
        'pending':  team_requests.filter(status='pending').count(),
        'approved': team_requests.filter(status__in=['manager_approved','approved']).count(),
        'rejected': team_requests.filter(status='rejected').count(),
        'total':    team_requests.count(),
    }

    team_members = User.objects.filter(profile__manager=request.user).select_related('profile')

    return render(request, 'leave_app/manager/dashboard.html', {
        'requests':     team_requests[:20],
        'stats':        stats,
        'team_members': team_members,
    })


@login_required(login_url='/login/')
def manager_review(request, pk):
    if get_role(request.user) != 'manager':
        return redirect('dashboard_redirect')

    leave_req = get_object_or_404(
        LeaveRequest, pk=pk, employee__profile__manager=request.user
    )

    if request.method == 'POST':
        action  = request.POST.get('action')
        comment = request.POST.get('comment', '').strip()

        if action == 'approve':
            leave_req.status              = 'manager_approved'
            leave_req.manager_reviewed_by = request.user
            leave_req.manager_comment     = comment
            leave_req.manager_reviewed_on = timezone.now()
            leave_req.save()
            send_notification(
                subject='Your leave request has been approved by your manager',
                message=(
                    f"Hi {leave_req.employee.get_full_name() or leave_req.employee.username},\n\n"
                    f"Your {leave_req.leave_type.name} leave from {leave_req.start_date} to "
                    f"{leave_req.end_date} has been approved by your manager.\n\n"
                    f"Manager comment: {comment or 'None'}\n\n"
                    f"It is now pending final approval from HR/Boss."
                ),
                recipient_email=leave_req.employee.email,
            )
            messages.success(request, 'Leave approved and forwarded for final review.')

        elif action == 'reject':
            leave_req.status              = 'rejected'
            leave_req.manager_reviewed_by = request.user
            leave_req.manager_comment     = comment
            leave_req.manager_reviewed_on = timezone.now()
            leave_req.save()
            send_notification(
                subject='Your leave request has been rejected',
                message=(
                    f"Hi {leave_req.employee.get_full_name() or leave_req.employee.username},\n\n"
                    f"Your {leave_req.leave_type.name} leave from {leave_req.start_date} to "
                    f"{leave_req.end_date} has been rejected by your manager.\n\n"
                    f"Reason: {comment or 'No reason provided.'}"
                ),
                recipient_email=leave_req.employee.email,
            )
            messages.warning(request, 'Leave request rejected.')

        return redirect('manager_dashboard')

    return render(request, 'leave_app/manager/review.html', {'leave_req': leave_req})


# ─────────────────────────────────────────────────────────────────────────────
# HR VIEWS
# ─────────────────────────────────────────────────────────────────────────────
@login_required(login_url='/login/')
def hr_dashboard(request):
    if get_role(request.user) != 'hr':
        return redirect('dashboard_redirect')

    all_requests = LeaveRequest.objects.select_related(
        'employee', 'leave_type', 'employee__profile'
    )
    status_filter = request.GET.get('status', '')
    if status_filter:
        all_requests = all_requests.filter(status=status_filter)

    stats = {
        'pending':          LeaveRequest.objects.filter(status='pending').count(),
        'manager_approved': LeaveRequest.objects.filter(status='manager_approved').count(),
        'approved':         LeaveRequest.objects.filter(status='approved').count(),
        'rejected':         LeaveRequest.objects.filter(status='rejected').count(),
        'total':            LeaveRequest.objects.count(),
    }

    employees = User.objects.filter(profile__role='employee').select_related('profile')

    return render(request, 'leave_app/hr/dashboard.html', {
        'requests':      all_requests,
        'stats':         stats,
        'employees':     employees,
        'status_filter': status_filter,
    })


@login_required(login_url='/login/')
def hr_review(request, pk):
    if get_role(request.user) not in ('hr', 'boss'):
        return redirect('dashboard_redirect')

    leave_req = get_object_or_404(LeaveRequest, pk=pk)

    if request.method == 'POST':
        action  = request.POST.get('action')
        comment = request.POST.get('comment', '').strip()
        now     = timezone.now()

        if action == 'approve':
            # Deduct from leave balance
            year = leave_req.start_date.year
            try:
                balance = LeaveBalance.objects.get(
                    employee=leave_req.employee,
                    leave_type=leave_req.leave_type,
                    year=year,
                )
                balance.used_days += leave_req.duration_days
                balance.save()
            except LeaveBalance.DoesNotExist:
                pass

            leave_req.status            = 'approved'
            leave_req.final_reviewed_by = request.user
            leave_req.final_comment     = comment
            leave_req.final_reviewed_on = now
            leave_req.save()
            send_notification(
                subject='Your leave request has been approved',
                message=(
                    f"Hi {leave_req.employee.get_full_name() or leave_req.employee.username},\n\n"
                    f"Great news! Your {leave_req.leave_type.name} leave from "
                    f"{leave_req.start_date} to {leave_req.end_date} ({leave_req.duration_days} day(s)) "
                    f"has been fully approved.\n\n"
                    f"Comment: {comment or 'None'}\n\nEnjoy your leave!"
                ),
                recipient_email=leave_req.employee.email,
            )
            messages.success(request, 'Leave fully approved. Balance deducted.')

        elif action == 'reject':
            leave_req.status            = 'rejected'
            leave_req.final_reviewed_by = request.user
            leave_req.final_comment     = comment
            leave_req.final_reviewed_on = now
            leave_req.save()
            send_notification(
                subject='Your leave request has been rejected',
                message=(
                    f"Hi {leave_req.employee.get_full_name() or leave_req.employee.username},\n\n"
                    f"Unfortunately, your {leave_req.leave_type.name} leave from "
                    f"{leave_req.start_date} to {leave_req.end_date} has been rejected.\n\n"
                    f"Reason: {comment or 'No reason provided.'}"
                ),
                recipient_email=leave_req.employee.email,
            )
            messages.warning(request, 'Leave request rejected.')

        return redirect('hr_dashboard' if get_role(request.user) == 'hr' else 'boss_dashboard')

    return render(request, 'leave_app/hr/review.html', {'leave_req': leave_req})


@login_required(login_url='/login/')
def add_employee(request):
    if get_role(request.user) not in ('hr', 'boss'):
        return redirect('dashboard_redirect')

    managers    = User.objects.filter(profile__role__in=['manager', 'hr', 'boss'])
    leave_types = LeaveType.objects.all()

    if request.method == 'POST':
        # User fields
        first_name  = request.POST.get('first_name', '').strip()
        last_name   = request.POST.get('last_name', '').strip()
        username    = request.POST.get('username', '').strip()
        email       = request.POST.get('email', '').strip()
        password    = request.POST.get('password', '').strip()

        # Profile fields
        role        = request.POST.get('role', 'employee')
        department  = request.POST.get('department', '').strip()
        employee_id = request.POST.get('employee_id', '').strip()
        phone       = request.POST.get('phone', '').strip()
        manager_id  = request.POST.get('manager')
        date_joined = request.POST.get('date_joined') or str(datetime.date.today())

        errors = []
        if not username:
            errors.append('Username is required.')
        elif User.objects.filter(username=username).exists():
            errors.append('Username already exists.')
        if not email:
            errors.append('Email is required.')
        elif User.objects.filter(email=email).exists():
            errors.append('Email already in use.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            # Update profile (auto-created via signal)
            profile           = user.profile
            profile.role      = role
            profile.department = department
            profile.employee_id = employee_id
            profile.phone     = phone
            profile.date_joined = date_joined
            if manager_id:
                try:
                    profile.manager = User.objects.get(pk=manager_id)
                except User.DoesNotExist:
                    pass
            profile.save()

            # Assign leave balances for current year
            year = datetime.date.today().year
            for lt in leave_types:
                LeaveBalance.objects.get_or_create(
                    employee=user, leave_type=lt, year=year,
                    defaults={'used_days': 0}
                )

            send_notification(
                subject='Welcome to Empleave',
                message=(
                    f"Hi {first_name or username},\n\n"
                    f"Your Empleave account has been created.\n\n"
                    f"Username: {username}\n"
                    f"Password: {password}\n\n"
                    f"Please log in at http://localhost:8000/login/ and change your password."
                ),
                recipient_email=email,
            )
            messages.success(request, f'Employee "{username}" created and leave balances assigned.')
            return redirect('hr_dashboard')

    return render(request, 'leave_app/hr/add_employee.html', {
        'managers':    managers,
        'leave_types': leave_types,
    })


# ─────────────────────────────────────────────────────────────────────────────
# BOSS VIEWS
# ─────────────────────────────────────────────────────────────────────────────
@login_required(login_url='/login/')
def boss_dashboard(request):
    if get_role(request.user) != 'boss':
        return redirect('dashboard_redirect')

    all_requests = LeaveRequest.objects.select_related(
        'employee', 'leave_type', 'employee__profile'
    )
    status_filter = request.GET.get('status', '')
    if status_filter:
        all_requests = all_requests.filter(status=status_filter)

    stats = {
        'pending':          LeaveRequest.objects.filter(status='pending').count(),
        'manager_approved': LeaveRequest.objects.filter(status='manager_approved').count(),
        'approved':         LeaveRequest.objects.filter(status='approved').count(),
        'rejected':         LeaveRequest.objects.filter(status='rejected').count(),
        'total':            LeaveRequest.objects.count(),
        'employees':        User.objects.filter(profile__role='employee').count(),
        'managers':         User.objects.filter(profile__role='manager').count(),
    }

    return render(request, 'leave_app/boss/dashboard.html', {
        'requests':      all_requests,
        'stats':         stats,
        'status_filter': status_filter,
    })
