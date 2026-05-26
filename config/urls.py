from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('campaigns/', include('campaigns.urls')),
    path('rulesets/', include('rulesets.urls')),
    path('options/', include('dnd_options.urls')),
    path('characters/', include('characters.urls')),
    path('ai-builder/', include('ai_builder.urls')),
    path('', RedirectView.as_view(pattern_name='campaigns:list', permanent=False)),
]
