from django.urls import path

from .views import (
    DNDOptionCreateView,
    DNDOptionImportPayloadView,
    DNDOptionListView,
    DNDOptionReviewDetailView,
    DNDOptionReviewQueueView,
    add_review_comment_view,
    apply_suggested_change_view,
    approve_suggested_change_view,
    propose_option_change_view,
    reject_suggested_change_view,
    resolve_review_view,
)

app_name = 'dnd_options'

urlpatterns = [
    path('', DNDOptionListView.as_view(), name='list'),
    path('create/', DNDOptionCreateView.as_view(), name='create'),
    path('import-json/', DNDOptionImportPayloadView.as_view(), name='import_json'),
    path('reviews/', DNDOptionReviewQueueView.as_view(), name='review_queue'),
    path('reviews/<int:pk>/', DNDOptionReviewDetailView.as_view(),
         name='review_detail'),
    path('reviews/<int:pk>/comments/add/',
         add_review_comment_view, name='add_review_comment'),
    path('reviews/<int:pk>/changes/add/',
         propose_option_change_view, name='propose_change'),
    path('reviews/<int:pk>/resolve/', resolve_review_view, name='resolve_review'),
    path('changes/<int:pk>/approve/',
         approve_suggested_change_view, name='approve_change'),
    path('changes/<int:pk>/reject/',
         reject_suggested_change_view, name='reject_change'),
    path('changes/<int:pk>/apply/',
         apply_suggested_change_view, name='apply_change'),
]
