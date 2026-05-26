from django.urls import path

from .views import AICharacterPromptView

app_name = 'ai_builder'

urlpatterns = [
    path('prompt/', AICharacterPromptView.as_view(), name='prompt'),
]
