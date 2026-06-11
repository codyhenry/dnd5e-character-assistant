from django.contrib import admin

from .models import DNDOption, DNDOptionReview, DNDOptionReviewComment, DNDOptionSuggestedChange
from .services import import_dnd_option_from_ai_payload


class DNDOptionReviewInline(admin.TabularInline):
    model = DNDOptionReview
    extra = 0
    fields = ('status', 'severity', 'reason', 'assigned_to', 'updated_at')
    readonly_fields = ('updated_at',)
    show_change_link = True


@admin.register(DNDOption)
class DNDOptionAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'option_type',
        'source_category',
        'needs_review',
        'review_status',
        'updated_at',
    )
    list_filter = (
        'option_type',
        'source_category',
        'needs_review',
        'review_status',
        'created_at',
        'updated_at',
    )
    search_fields = (
        'name',
        'source_url',
        'summary',
        'description',
        'review_reasons',
        'mechanical_tags',
        'visual_or_flavor_tags',
    )
    readonly_fields = ('created_at', 'updated_at', 'reviewed_at')
    autocomplete_fields = ('parent_option', 'reviewed_by')
    ordering = ('name',)
    inlines = (DNDOptionReviewInline,)

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


class DNDOptionReviewCommentInline(admin.TabularInline):
    model = DNDOptionReviewComment
    extra = 0
    fields = ('author', 'visibility', 'target_path', 'comment', 'created_at')
    readonly_fields = ('created_at',)
    show_change_link = True


class DNDOptionSuggestedChangeInline(admin.TabularInline):
    model = DNDOptionSuggestedChange
    extra = 0
    fields = ('operation', 'target_path', 'status', 'proposed_by', 'reviewed_by', 'applied_by', 'created_at')
    readonly_fields = ('created_at',)
    show_change_link = True


@admin.register(DNDOptionReview)
class DNDOptionReviewAdmin(admin.ModelAdmin):
    list_display = (
        'dnd_option',
        'option_type',
        'source_category',
        'status',
        'severity',
        'assigned_to',
        'updated_at',
    )
    list_filter = (
        'status',
        'severity',
        'dnd_option__option_type',
        'dnd_option__source_category',
        'assigned_to',
        'created_at',
        'updated_at',
        'resolved_at',
    )
    search_fields = (
        'dnd_option__name',
        'dnd_option__source_url',
        'reason',
        'ai_review_reasons',
        'resolution_notes',
    )
    readonly_fields = ('created_at', 'updated_at', 'resolved_at')
    autocomplete_fields = ('dnd_option', 'opened_by', 'assigned_to', 'resolved_by')
    ordering = ('-updated_at',)
    inlines = (DNDOptionReviewCommentInline, DNDOptionSuggestedChangeInline)

    @admin.display(description='Option type', ordering='dnd_option__option_type')
    def option_type(self, obj):
        return obj.dnd_option.option_type

    @admin.display(description='Source category', ordering='dnd_option__source_category')
    def source_category(self, obj):
        return obj.dnd_option.source_category


@admin.register(DNDOptionReviewComment)
class DNDOptionReviewCommentAdmin(admin.ModelAdmin):
    list_display = ('review', 'author', 'visibility', 'target_path', 'created_at')
    list_filter = ('visibility', 'created_at', 'updated_at')
    search_fields = ('review__dnd_option__name', 'author__username', 'comment', 'target_path')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('review', 'author')
    ordering = ('-created_at',)


@admin.register(DNDOptionSuggestedChange)
class DNDOptionSuggestedChangeAdmin(admin.ModelAdmin):
    list_display = (
        'review',
        'operation',
        'target_path',
        'status',
        'proposed_by',
        'reviewed_by',
        'applied_by',
        'created_at',
    )
    list_filter = ('operation', 'status', 'created_at', 'reviewed_at', 'applied_at')
    search_fields = ('review__dnd_option__name', 'target_path', 'reason', 'rejection_reason')
    readonly_fields = ('created_at', 'updated_at', 'reviewed_at', 'applied_at')
    autocomplete_fields = ('review', 'proposed_by', 'reviewed_by', 'applied_by')
    ordering = ('-created_at',)
