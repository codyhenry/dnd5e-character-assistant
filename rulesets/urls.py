from django.urls import path

from .views import RulesetCreateView, RulesetDetailView, RulesetUpdateView

app_name = 'rulesets'

urlpatterns = [
    path('<int:pk>/', RulesetDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', RulesetUpdateView.as_view(), name='edit'),
    path('campaign/<int:campaign_pk>/create/', RulesetCreateView.as_view(), name='create'),
]
