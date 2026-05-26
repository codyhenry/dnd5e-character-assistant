from django.urls import path

from .views import (
    CampaignCreateView,
    CampaignDetailView,
    CampaignListView,
    CampaignMembershipManageView,
    CampaignUpdateView,
    DMCampaignDashboardView,
)

app_name = 'campaigns'

urlpatterns = [
    path('', CampaignListView.as_view(), name='list'),
    path('create/', CampaignCreateView.as_view(), name='create'),
    path('<int:pk>/', CampaignDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', CampaignUpdateView.as_view(), name='edit'),
    path('<int:pk>/dm-dashboard/', DMCampaignDashboardView.as_view(), name='dm_dashboard'),
    path('<int:pk>/members/', CampaignMembershipManageView.as_view(), name='manage_members'),
]
