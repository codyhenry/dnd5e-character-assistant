from django.urls import path

from .views import (
    CharacterBuildCreateView,
    CharacterBuildDetailView,
    CharacterBuildListView,
    CharacterBuildUpdateView,
    DMAllBuildsView,
    NPCCreateView,
    PlayerDashboardView,
)

app_name = 'characters'

urlpatterns = [
    path('dashboard/', PlayerDashboardView.as_view(), name='player_dashboard'),
    path('', CharacterBuildListView.as_view(), name='list'),
    path('create/', CharacterBuildCreateView.as_view(), name='create'),
    path('npc/create/', NPCCreateView.as_view(), name='npc_create'),
    path('<int:pk>/', CharacterBuildDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', CharacterBuildUpdateView.as_view(), name='edit'),
    path('campaign/<int:campaign_pk>/all/', DMAllBuildsView.as_view(), name='dm_all_builds'),
]
