from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, FormView, ListView

from campaigns.models import CampaignMembership

from .forms import (
    DNDOptionForm,
    DNDOptionImportPayloadForm,
    DNDOptionReviewCommentForm,
    DNDOptionSuggestedChangeForm,
    RejectionReasonForm,
    ReviewResolutionForm,
)
from .json_path import get_value_at_path, validate_json_path
from .models import DNDOption, DNDOptionReview, DNDOptionReviewComment, DNDOptionSuggestedChange
from .review_services import (
    add_review_comment,
    apply_suggested_change,
    approve_suggested_change,
    get_snapshot_for_path,
    propose_option_change,
    reject_suggested_change,
    resolve_review,
)
from .services import import_dnd_option_from_ai_payload


OPEN_REVIEW_STATUSES = [
    DNDOptionReview.Status.OPEN,
    DNDOptionReview.Status.IN_REVIEW,
    DNDOptionReview.Status.CHANGES_REQUESTED,
]


def _is_dm_or_admin(user) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return CampaignMembership.objects.filter(user=user, role=CampaignMembership.Role.DM).exists()


class DNDOptionListView(LoginRequiredMixin, ListView):
    model = DNDOption
    template_name = 'dnd_options/option_list.html'


class DNDOptionCreateView(LoginRequiredMixin, CreateView):
    model = DNDOption
    form_class = DNDOptionForm
    template_name = 'dnd_options/option_form.html'
    success_url = reverse_lazy('dnd_options:list')

    def form_valid(self, form):
        payload = {
            'name': form.cleaned_data['name'],
            'type': form.cleaned_data['option_type'],
            'parent': form.cleaned_data['parent_option'].name if form.cleaned_data['parent_option'] else None,
            'source_url': form.cleaned_data['source_url'],
            'source_category': form.cleaned_data['source_category'],
            'description': form.cleaned_data['description'],
            'summary': form.cleaned_data['summary'],
            'prerequisites': form.cleaned_data['prerequisites'],
            'traits': form.cleaned_data['traits'],
            'normalized_data': form.cleaned_data['normalized_data'],
            'primary_ability_scores': form.cleaned_data['primary_ability_scores'],
            'mechanical_tags': form.cleaned_data['mechanical_tags'],
            'visual_or_flavor_tags': form.cleaned_data['visual_or_flavor_tags'],
            'build_notes': form.cleaned_data['build_notes'],
            'review_reasons': form.cleaned_data['review_reasons'],
            'needs_review': form.cleaned_data['needs_review'],
        }
        import_dnd_option_from_ai_payload(payload, opened_by=self.request.user)
        return redirect('dnd_options:list')


class DNDOptionImportPayloadView(LoginRequiredMixin, FormView):
    template_name = 'dnd_options/import_payload.html'
    form_class = DNDOptionImportPayloadForm
    success_url = reverse_lazy('dnd_options:list')

    def form_valid(self, form):
        payload = form.cleaned_data['payload']
        import_dnd_option_from_ai_payload(payload, opened_by=self.request.user)
        messages.success(self.request, 'D&D option imported.')
        return super().form_valid(form)


class DNDOptionReviewQueueView(LoginRequiredMixin, ListView):
    model = DNDOptionReview
    template_name = 'dnd_options/review_queue.html'
    context_object_name = 'reviews'

    def get_queryset(self):
        queryset = DNDOptionReview.objects.select_related('dnd_option', 'assigned_to').filter(
            status__in=OPEN_REVIEW_STATUSES
        )

        query = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', '').strip()
        severity = self.request.GET.get('severity', '').strip()
        option_type = self.request.GET.get('option_type', '').strip()
        source_category = self.request.GET.get('source_category', '').strip()

        if query:
            queryset = queryset.filter(
                Q(dnd_option__name__icontains=query) |
                Q(dnd_option__source_url__icontains=query) |
                Q(reason__icontains=query) |
                Q(ai_review_reasons__icontains=query)
            )
        if status:
            queryset = queryset.filter(status=status)
        if severity:
            queryset = queryset.filter(severity=severity)
        if option_type:
            queryset = queryset.filter(dnd_option__option_type=option_type)
        if source_category:
            queryset = queryset.filter(dnd_option__source_category=source_category)

        return queryset.order_by('-updated_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filters'] = {
            'q': self.request.GET.get('q', '').strip(),
            'status': self.request.GET.get('status', '').strip(),
            'severity': self.request.GET.get('severity', '').strip(),
            'option_type': self.request.GET.get('option_type', '').strip(),
            'source_category': self.request.GET.get('source_category', '').strip(),
        }
        context['status_choices'] = [
            choice for choice in DNDOptionReview.Status.choices
            if choice[0] in OPEN_REVIEW_STATUSES
        ]
        context['severity_choices'] = DNDOptionReview.Severity.choices
        context['option_type_choices'] = DNDOption.OptionType.choices
        context['source_category_choices'] = DNDOption.SourceCategory.choices
        return context


class DNDOptionReviewDetailView(LoginRequiredMixin, DetailView):
    model = DNDOptionReview
    template_name = 'dnd_options/review_detail.html'
    context_object_name = 'review'
    object: DNDOptionReview

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        review = self.object

        can_manage = _is_dm_or_admin(self.request.user)
        comment_form = kwargs.get(
            'comment_form') or DNDOptionReviewCommentForm()
        suggested_change_form = kwargs.get(
            'suggested_change_form') or DNDOptionSuggestedChangeForm()
        resolution_form = kwargs.get(
            'resolution_form') or ReviewResolutionForm()
        rejection_form = kwargs.get('rejection_form') or RejectionReasonForm()

        comments = review.comments.select_related('author').all()
        if not self.request.user.is_staff:
            comments = comments.exclude(
                visibility=DNDOptionReviewComment.Visibility.ADMIN_ONLY)
        if not can_manage:
            comments = comments.exclude(
                visibility=DNDOptionReviewComment.Visibility.DM_ONLY)

        preview_path = self.request.GET.get('preview_path', '').strip()
        preview_value = None
        preview_error = None
        if preview_path:
            if validate_json_path(preview_path):
                try:
                    preview_value = get_snapshot_for_path(
                        review.dnd_option, preview_path)
                except (KeyError, IndexError) as exc:
                    preview_error = str(exc)
            else:
                preview_error = 'Invalid path syntax.'

        context.update(
            {
                'can_manage_reviews': can_manage,
                'comment_form': comment_form,
                'suggested_change_form': suggested_change_form,
                'resolution_form': resolution_form,
                'rejection_form': rejection_form,
                'comments': comments,
                'suggested_changes': review.suggested_changes.select_related('proposed_by', 'reviewed_by', 'applied_by').all(),
                'review_document': review.dnd_option.normalized_data,
                'preview_path': preview_path,
                'preview_value': preview_value,
                'preview_error': preview_error,
            }
        )
        return context


@login_required
def add_review_comment_view(request, pk):
    review = get_object_or_404(DNDOptionReview, pk=pk)
    if request.method != 'POST':
        return redirect('dnd_options:review_detail', pk=pk)

    form = DNDOptionReviewCommentForm(request.POST)
    if form.is_valid():
        visibility = form.cleaned_data['visibility']
        if visibility in {DNDOptionReviewComment.Visibility.ADMIN_ONLY, DNDOptionReviewComment.Visibility.DM_ONLY} and not _is_dm_or_admin(request.user):
            return HttpResponseForbidden('Only DMs/admins may create restricted comments.')
        add_review_comment(
            review,
            author=request.user,
            comment=form.cleaned_data['comment'],
            target_path=form.cleaned_data.get('target_path') or None,
            visibility=visibility,
        )
        return redirect('dnd_options:review_detail', pk=pk)

    detail_view = DNDOptionReviewDetailView()
    detail_view.request = request
    detail_view.object = review
    context = detail_view.get_context_data(comment_form=form)
    return render(request, 'dnd_options/review_detail.html', context)


@login_required
def propose_option_change_view(request, pk):
    review = get_object_or_404(DNDOptionReview, pk=pk)
    if request.method != 'POST':
        return redirect('dnd_options:review_detail', pk=pk)

    form = DNDOptionSuggestedChangeForm(request.POST)
    if form.is_valid():
        try:
            propose_option_change(
                review,
                proposed_by=request.user,
                target_path=form.cleaned_data['target_path'],
                operation=form.cleaned_data['operation'],
                proposed_value=form.cleaned_data['parsed_proposed_value'],
                reason=form.cleaned_data['reason'],
            )
            return redirect('dnd_options:review_detail', pk=pk)
        except ValidationError as exc:
            form.add_error(None, exc)

    detail_view = DNDOptionReviewDetailView()
    detail_view.request = request
    detail_view.object = review
    context = detail_view.get_context_data(suggested_change_form=form)
    return render(request, 'dnd_options/review_detail.html', context)


@login_required
def approve_suggested_change_view(request, pk):
    suggested_change = get_object_or_404(DNDOptionSuggestedChange, pk=pk)
    if not _is_dm_or_admin(request.user):
        return HttpResponseForbidden('Only DMs/admins can approve changes.')
    approve_suggested_change(suggested_change, request.user)
    return redirect('dnd_options:review_detail', pk=suggested_change.review_id)


@login_required
def reject_suggested_change_view(request, pk):
    suggested_change = get_object_or_404(DNDOptionSuggestedChange, pk=pk)
    if not _is_dm_or_admin(request.user):
        return HttpResponseForbidden('Only DMs/admins can reject changes.')

    form = RejectionReasonForm(request.POST)
    if form.is_valid():
        reject_suggested_change(
            suggested_change, request.user, form.cleaned_data['reason'])
    return redirect('dnd_options:review_detail', pk=suggested_change.review_id)


@login_required
def apply_suggested_change_view(request, pk):
    suggested_change = get_object_or_404(DNDOptionSuggestedChange, pk=pk)
    if not _is_dm_or_admin(request.user):
        return HttpResponseForbidden('Only DMs/admins can apply changes.')
    try:
        apply_suggested_change(suggested_change, request.user)
    except ValidationError as exc:
        messages.error(request, str(exc))
    return redirect('dnd_options:review_detail', pk=suggested_change.review_id)


@login_required
def resolve_review_view(request, pk):
    review = get_object_or_404(DNDOptionReview, pk=pk)
    if not _is_dm_or_admin(request.user):
        return HttpResponseForbidden('Only DMs/admins can resolve reviews.')

    form = ReviewResolutionForm(request.POST)
    if form.is_valid():
        resolve_review(
            review,
            resolver=request.user,
            status=form.cleaned_data['status'],
            resolution_notes=form.cleaned_data['resolution_notes'],
        )
    return redirect('dnd_options:review_detail', pk=pk)
