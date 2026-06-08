from django.urls import path

from .views import (
    RulesetCreateView,
    RulesetDetailView,
    RulesetUpdateView,
    add_option_restriction_view,
    remove_option_restriction_view,
)

app_name = 'rulesets'

urlpatterns = [
    path('<int:pk>/', RulesetDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', RulesetUpdateView.as_view(), name='edit'),
    path('<int:pk>/option-restrictions/add/', add_option_restriction_view, name='add_option_restriction'),
    path(
        '<int:pk>/option-restrictions/<int:restriction_pk>/remove/',
        remove_option_restriction_view,
        name='remove_option_restriction',
    ),
    path('campaign/<int:campaign_pk>/create/', RulesetCreateView.as_view(), name='create'),
]
