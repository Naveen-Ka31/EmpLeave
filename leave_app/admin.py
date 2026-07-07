from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, LeaveType, LeaveBalance, LeaveRequest


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    fk_name = 'user'
    can_delete = False
    verbose_name_plural = 'Profile'


class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'get_full_name', 'get_role', 'get_dept', 'is_active')
    list_filter  = ('profile__role', 'is_active', 'is_staff')

    def get_role(self, obj):
        try: return obj.profile.get_role_display()
        except: return '—'
    get_role.short_description = 'Role'

    def get_dept(self, obj):
        try: return obj.profile.department
        except: return '—'
    get_dept.short_description = 'Department'


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'total_days', 'description')


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'leave_type', 'year', 'used_days', 'get_remaining')
    list_filter   = ('leave_type', 'year')
    search_fields = ('employee__username', 'employee__first_name')

    def get_remaining(self, obj):
        return obj.remaining_days
    get_remaining.short_description = 'Remaining'


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'leave_type', 'start_date', 'end_date', 'duration_days', 'status', 'applied_on')
    list_filter   = ('status', 'leave_type', 'applied_on')
    search_fields = ('employee__username', 'employee__first_name', 'reason')
    readonly_fields = ('applied_on', 'manager_reviewed_on', 'final_reviewed_on')

    def duration_days(self, obj):
        return f"{obj.duration_days} day(s)"
    duration_days.short_description = 'Duration'
