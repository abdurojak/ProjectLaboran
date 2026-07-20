from django.urls import path

from .views import (
    AttendanceHistoryView,
    ChatbotView,
    CheckInView,
    DashboardView,
    LocationConfigView,
    LaboranDashboardView,
    LaboranInventoryListCreateView,
    LaboranLoanListView,
    LaboranLoanStatusView,
    LaboranLocationListView,
    LoginView,
    LogoutView,
    ProfileView,
    RefreshTokenView,
    ScheduleDetailView,
    ScheduleListView,
)

app_name = 'mobile_api'

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/refresh/', RefreshTokenView.as_view(), name='refresh'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('schedules/', ScheduleListView.as_view(), name='schedule_list'),
    path('schedules/<int:pk>/', ScheduleDetailView.as_view(), name='schedule_detail'),
    path('attendance/check-in/', CheckInView.as_view(), name='check_in'),
    path('attendance/history/', AttendanceHistoryView.as_view(), name='attendance_history'),
    path('chatbot/', ChatbotView.as_view(), name='chatbot'),
    path('config/location/', LocationConfigView.as_view(), name='location_config'),
    path('laboran/dashboard/', LaboranDashboardView.as_view(), name='laboran_dashboard'),
    path('laboran/locations/', LaboranLocationListView.as_view(), name='laboran_locations'),
    path('laboran/inventory/', LaboranInventoryListCreateView.as_view(), name='laboran_inventory'),
    path('laboran/loans/', LaboranLoanListView.as_view(), name='laboran_loans'),
    path('laboran/loans/<int:pk>/status/', LaboranLoanStatusView.as_view(), name='laboran_loan_status'),
]
