from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import datetime


# ─────────────────────────────────────────────────────────────────────────────
# USER PROFILE
# Extends Django's built-in User with role, department, manager link
# ─────────────────────────────────────────────────────────────────────────────
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('employee', 'Employee'),
        ('manager',  'Manager'),
        ('hr',       'HR'),
        ('boss',     'Boss'),
    ]

    user        = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role        = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    department  = models.CharField(max_length=100, blank=True)
    employee_id = models.CharField(max_length=20, blank=True)
    phone       = models.CharField(max_length=15, blank=True)
    date_joined = models.DateField(default=datetime.date.today)

    # Employees are assigned to a manager
    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='team_members',
        limit_choices_to={'profile__role__in': ['manager', 'hr', 'boss']}
    )

    def __str__(self):
        name = self.user.get_full_name() or self.user.username
        return f"{name} ({self.get_role_display()})"

    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.username


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


# ─────────────────────────────────────────────────────────────────────────────
# LEAVE TYPE
# e.g. Casual Leave (12 days), Sick Leave (10 days), Earned Leave (15 days)
# ─────────────────────────────────────────────────────────────────────────────
class LeaveType(models.Model):
    name        = models.CharField(max_length=50, unique=True)
    total_days  = models.PositiveIntegerField(default=12)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.total_days} days/year)"


# ─────────────────────────────────────────────────────────────────────────────
# LEAVE BALANCE
# Tracks each employee's used/remaining days per leave type per year
# ─────────────────────────────────────────────────────────────────────────────
class LeaveBalance(models.Model):
    employee   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_balances')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    used_days  = models.PositiveIntegerField(default=0)
    year       = models.PositiveIntegerField(default=datetime.date.today().year)

    class Meta:
        unique_together = ('employee', 'leave_type', 'year')

    @property
    def remaining_days(self):
        return max(self.leave_type.total_days - self.used_days, 0)

    @property
    def usage_percent(self):
        if self.leave_type.total_days == 0:
            return 0
        return min(int((self.used_days / self.leave_type.total_days) * 100), 100)

    def __str__(self):
        return f"{self.employee.username} | {self.leave_type.name} | {self.remaining_days} left ({self.year})"


# ─────────────────────────────────────────────────────────────────────────────
# LEAVE REQUEST
# Core workflow: Employee → Manager → HR/Boss
# ─────────────────────────────────────────────────────────────────────────────
class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ('pending',          'Pending'),
        ('manager_approved', 'Approved by Manager'),
        ('forwarded_hr',     'Forwarded to HR'),
        ('approved',         'Approved'),
        ('rejected',         'Rejected'),
    ]

    employee   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.SET_NULL, null=True)
    start_date = models.DateField()
    end_date   = models.DateField()
    reason     = models.TextField()
    status     = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    applied_on = models.DateTimeField(auto_now_add=True)

    # Manager level review
    manager_reviewed_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='manager_reviews'
    )
    manager_comment      = models.TextField(blank=True)
    manager_reviewed_on  = models.DateTimeField(null=True, blank=True)

    # HR / Boss final review
    final_reviewed_by    = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='final_reviews'
    )
    final_comment        = models.TextField(blank=True)
    final_reviewed_on    = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-applied_on']

    def __str__(self):
        lt = self.leave_type.name if self.leave_type else 'Leave'
        return f"{self.employee.username} | {lt} | {self.start_date} | {self.status}"

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1

    @property
    def status_badge(self):
        badges = {
            'pending':          'warning',
            'manager_approved': 'info',
            'forwarded_hr':     'secondary',
            'approved':         'success',
            'rejected':         'danger',
        }
        return badges.get(self.status, 'secondary')
