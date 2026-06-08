from django.contrib import admin

from .models import DNDOption, DNDOptionReview, DNDOptionReviewComment, DNDOptionSuggestedChange
from .services import import_dnd_option_from_ai_payload


@admin.register(DNDOption)
class DNDOptionAdmin(admin.ModelAdmin):
    list_display = ('name', 'option_type', 'source_category',
                    'needs_review', 'review_status')
    search_fields = ('name', 'source_url')

    def save_model(self, request, obj, form, change):
        payload = {
            'name': form.cleaned_data['name'],
            'type': form.cleaned_data['option_type'],
            'parent': form.cleaned_data['parent_option'].name if form.cleaned_data['parent_option'] else None,
            'source_url': form.cleaned_data.get('source_url', ''),
            'source_category': form.cleaned_data['source_category'],
            'description': form.cleaned_data.get('description', ''),
            'summary': form.cleaned_data.get('summary', ''),
            'prerequisites': form.cleaned_data.get('prerequisites') or {},
            'traits': form.cleaned_data.get('traits') or {},
            'normalized_data': form.cleaned_data.get('normalized_data') or {},
            'primary_ability_scores': form.cleaned_data.get('primary_ability_scores') or [],
            'mechanical_tags': form.cleaned_data.get('mechanical_tags') or [],
            'visual_or_flavor_tags': form.cleaned_data.get('visual_or_flavor_tags') or [],
            'build_notes': form.cleaned_data.get('build_notes') or [],
            'review_reasons': form.cleaned_data.get('review_reasons') or [],
            'needs_review': form.cleaned_data.get('needs_review', False),
        }
        import_dnd_option_from_ai_payload(payload, opened_by=request.user)


@admin.register(DNDOptionReview)
class DNDOptionReviewAdmin(admin.ModelAdmin):
    list_display = ('dnd_option', 'status', 'severity', 'updated_at')
    search_fields = ('dnd_option__name', 'reason')


@admin.register(DNDOptionReviewComment)
class DNDOptionReviewCommentAdmin(admin.ModelAdmin):
    list_display = ('review', 'author', 'visibility',
                    'target_path', 'created_at')


@admin.register(DNDOptionSuggestedChange)
class DNDOptionSuggestedChangeAdmin(admin.ModelAdmin):
    list_display = ('review', 'operation', 'target_path',
                    'status', 'created_at')
