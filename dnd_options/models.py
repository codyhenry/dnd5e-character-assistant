from typing import TYPE_CHECKING, Any

from django.db import models
from django.conf import settings


class DNDOption(models.Model):
    if TYPE_CHECKING:
        id: int
        # Reverse relation from DNDOptionReview.dnd_option (related_name='reviews').
        reviews: Any
        parent_option: Any
        parent_option_id: int | None
        _previous_content_snapshot: dict[str, Any] | None

    class OptionType(models.TextChoices):
        CLASS = 'CLASS', 'Class'
        SUBCLASS = 'SUBCLASS', 'Subclass'
        SPECIES = 'SPECIES', 'Species/Race/Lineage'
        BACKGROUND = 'BACKGROUND', 'Background'
        FEAT = 'FEAT', 'Feat'
        SPELL = 'SPELL', 'Spell'
        EQUIPMENT = 'EQUIPMENT', 'Equipment'
        FEATURE = 'FEATURE', 'Feature/Trait'
        ATTACK = 'ATTACK', 'Attack/Action'
        FIGHTING_STYLE = 'FIGHTING_STYLE', 'Fighting Style'
        INVOCATION = 'INVOCATION', 'Invocation'
        MANEUVER = 'MANEUVER', 'Maneuver'
        OTHER = 'OTHER', 'Other'

    class SourceCategory(models.TextChoices):
        OFFICIAL = 'official', 'Official'
        SETTING_SPECIFIC = 'setting-specific', 'Setting Specific'
        UNEARTHED_ARCANA = 'unearthed-arcana', 'Unearthed Arcana'
        HOMEBREW = 'homebrew', 'Homebrew'
        CUSTOM = 'custom', 'Custom'

    class ReviewStatus(models.TextChoices):
        CLEAN = 'CLEAN', 'Clean'
        NEEDS_REVIEW = 'NEEDS_REVIEW', 'Needs Review'
        IN_REVIEW = 'IN_REVIEW', 'In Review'
        REVIEWED = 'REVIEWED', 'Reviewed'

    name = models.CharField(max_length=255)
    option_type = models.CharField(max_length=30, choices=OptionType.choices)
    parent_option = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='child_options')
    source_url = models.URLField(blank=True)
    source_category = models.CharField(
        max_length=50, choices=SourceCategory.choices, default=SourceCategory.OFFICIAL)
    description = models.TextField(blank=True)
    prerequisites = models.JSONField(default=dict, blank=True)
    traits = models.JSONField(default=dict, blank=True)
    summary = models.TextField(blank=True)
    primary_ability_scores = models.JSONField(default=list, blank=True)
    mechanical_tags = models.JSONField(default=list, blank=True)
    visual_or_flavor_tags = models.JSONField(default=list, blank=True)
    build_notes = models.JSONField(default=list, blank=True)
    review_reasons = models.JSONField(default=list, blank=True)
    normalized_data = models.JSONField(default=dict, blank=True)
    needs_review = models.BooleanField(default=False)
    review_status = models.CharField(
        max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.CLEAN)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_dnd_options',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.option_type})'


class DNDOptionReview(models.Model):
    if TYPE_CHECKING:
        # Reverse relation from DNDOptionReviewComment.review.
        comments: Any
        # Reverse relation from DNDOptionSuggestedChange.review.
        suggested_changes: Any

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_REVIEW = 'IN_REVIEW', 'In Review'
        CHANGES_REQUESTED = 'CHANGES_REQUESTED', 'Changes Requested'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        NO_CHANGE_NEEDED = 'NO_CHANGE_NEEDED', 'No Change Needed'
        CLOSED = 'CLOSED', 'Closed'

    class Severity(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'

    dnd_option = models.ForeignKey(
        DNDOption, on_delete=models.CASCADE, related_name='reviews')
    status = models.CharField(
        max_length=25, choices=Status.choices, default=Status.OPEN)
    severity = models.CharField(
        max_length=10, choices=Severity.choices, default=Severity.LOW)
    reason = models.CharField(max_length=255)
    ai_review_reasons = models.JSONField(default=list, blank=True)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='opened_dnd_option_reviews',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_dnd_option_reviews',
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_dnd_option_reviews',
    )
    resolution_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'Review for {self.dnd_option.name} ({self.status})'


class DNDOptionReviewComment(models.Model):
    class Visibility(models.TextChoices):
        PUBLIC = 'PUBLIC', 'Public'
        DM_ONLY = 'DM_ONLY', 'DM Only'
        ADMIN_ONLY = 'ADMIN_ONLY', 'Admin Only'

    review = models.ForeignKey(
        DNDOptionReview, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dnd_option_review_comments')
    comment = models.TextField()
    target_path = models.CharField(max_length=255, null=True, blank=True)
    target_snapshot = models.JSONField(null=True, blank=True)
    visibility = models.CharField(
        max_length=15, choices=Visibility.choices, default=Visibility.PUBLIC)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']


class DNDOptionSuggestedChange(models.Model):
    if TYPE_CHECKING:
        review: Any
        review_id: int

    class Operation(models.TextChoices):
        REPLACE = 'REPLACE', 'Replace'
        ADD = 'ADD', 'Add'
        REMOVE = 'REMOVE', 'Remove'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        APPLIED = 'APPLIED', 'Applied'

    review = models.ForeignKey(
        DNDOptionReview, on_delete=models.CASCADE, related_name='suggested_changes')
    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dnd_option_suggested_changes')
    target_path = models.CharField(max_length=255)
    current_value = models.JSONField(null=True, blank=True)
    proposed_value = models.JSONField(null=True, blank=True)
    operation = models.CharField(max_length=10, choices=Operation.choices)
    reason = models.TextField()
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_dnd_option_suggested_changes',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='applied_dnd_option_suggested_changes',
    )
    applied_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
