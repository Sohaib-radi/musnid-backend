"""URL configuration of API v1. Public identifiers only: center slug, membership uuid, question uuid."""

from django.urls import path

from api.v1.views import auth, centers, memberships, questions, telegram

app_name = 'v1'

urlpatterns = [
    path('auth/register/', auth.RegisterView.as_view(), name='register'),
    path('auth/register/center/', auth.CenterRegisterView.as_view(), name='register-center'),
    path('auth/login/', auth.LoginView.as_view(), name='login'),
    path('auth/refresh/', auth.RefreshView.as_view(), name='refresh'),
    path('auth/logout/', auth.LogoutView.as_view(), name='logout'),
    path('me/', auth.MeView.as_view(), name='me'),
    path('me/memberships/', auth.MyMembershipsView.as_view(), name='my-memberships'),
    path('me/questions/', questions.MyQuestionsView.as_view(), name='my-questions'),
    path('questions/', questions.QuestionListCreateView.as_view(), name='questions'),
    path('questions/<uuid:uuid>/', questions.QuestionDetailView.as_view(), name='question'),
    path('countries/', centers.CountryListView.as_view(), name='countries'),
    path('centers/<slug:slug>/', centers.CenterDetailView.as_view(), name='center'),
    path('centers/<slug:slug>/dashboard/', centers.CenterDashboardView.as_view(), name='center-dashboard'),
    path('centers/<slug:slug>/settings/', centers.CenterSettingsView.as_view(), name='center-settings'),
    path('centers/<slug:slug>/telegram/', telegram.TelegramStatusView.as_view(), name='center-telegram'),
    path('centers/<slug:slug>/telegram/connect/', telegram.TelegramConnectView.as_view(),
         name='center-telegram-connect'),
    path('centers/<slug:slug>/telegram/disconnect/', telegram.TelegramDisconnectView.as_view(),
         name='center-telegram-disconnect'),
    path('centers/<slug:slug>/memberships/', memberships.MembershipListView.as_view(), name='memberships'),
    path('centers/<slug:slug>/memberships/<uuid:uuid>/', memberships.MembershipDetailView.as_view(),
         name='membership'),
    path('centers/<slug:slug>/memberships/<uuid:uuid>/offboard/', memberships.MembershipOffboardView.as_view(),
         name='membership-offboard'),
]
