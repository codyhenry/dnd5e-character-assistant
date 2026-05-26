from django.urls import path

from .views import DNDOptionCreateView, DNDOptionListView

app_name = 'dnd_options'

urlpatterns = [
    path('', DNDOptionListView.as_view(), name='list'),
    path('create/', DNDOptionCreateView.as_view(), name='create'),
]
