from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView
from typing import cast

from campaigns.models import Campaign
from campaigns.permissions import can_create_npc, can_view_build, is_campaign_dm

from .forms import CharacterBuildForm
from .models import CharacterBuild
from .selectors import (
    build_validation_summary,
    builds_requiring_validation_attention,
    campaign_builds_for_dm,
    visible_builds_for_user,
)
from .services import (
    build_character_sheet_context,
    revalidate_character_build,
    require_valid_build_for_reuse,
    sync_selected_options_for_build,
)


class PlayerDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'characters/player_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['campaigns'] = Campaign.objects.filter(
            memberships__user=self.request.user).distinct()
        builds = visible_builds_for_user(self.request.user)
        context['builds'] = builds
        context['validation_summary'] = build_validation_summary(builds)
        context['builds_requiring_attention'] = builds_requiring_validation_attention(
            builds
        ).order_by('-updated_at')
        return context


class CharacterBuildListView(LoginRequiredMixin, ListView):
    model = CharacterBuild
    template_name = 'characters/build_list.html'

    def get_queryset(self):
        return visible_builds_for_user(self.request.user)


class CharacterBuildDetailView(LoginRequiredMixin, DetailView):
    model = CharacterBuild
    template_name = 'characters/build_detail.html'
    object: CharacterBuild

    def dispatch(self, request, *args, **kwargs):
        build = self.get_object()
        if not can_view_build(request.user, build):
            return HttpResponseForbidden('You cannot view this build.')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sheet'] = build_character_sheet_context(self.object)

        # Add campaign build navigation for DMs
        campaign = self.object.campaign
        if is_campaign_dm(self.request.user, campaign):
            campaign_builds = campaign_builds_for_dm(
                self.request.user, campaign).order_by('name')
            context['campaign_builds'] = campaign_builds

            # Find current build's position
            build_list = list(campaign_builds.values_list('pk', flat=True))
            if self.object.pk in build_list:
                current_index = build_list.index(self.object.pk)
                if current_index > 0:
                    context['prev_build_id'] = build_list[current_index - 1]
                if current_index < len(build_list) - 1:
                    context['next_build_id'] = build_list[current_index + 1]

        return context


class CharacterBuildCreateView(LoginRequiredMixin, CreateView):
    model = CharacterBuild
    form_class = CharacterBuildForm
    template_name = 'characters/build_form.html'
    object: CharacterBuild

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        campaign_pk = self.request.GET.get('campaign')
        if campaign_pk:
            initial['campaign'] = campaign_pk
        return initial

    def form_valid(self, form):
        campaign = form.cleaned_data['campaign']
        build_type = form.cleaned_data['build_type']
        if not campaign.memberships.filter(user=self.request.user).exists():
            return HttpResponseForbidden('You must be a campaign member to create a build.')
        if build_type == CharacterBuild.BuildType.NPC and not can_create_npc(self.request.user, campaign):
            return HttpResponseForbidden('Only DMs can create NPCs.')
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        sync_selected_options_for_build(self.object)
        return response

    def get_success_url(self):
        return reverse('characters:detail', args=[self.object.pk])


class CharacterBuildUpdateView(LoginRequiredMixin, UpdateView):
    model = CharacterBuild
    form_class = CharacterBuildForm
    template_name = 'characters/build_form.html'
    object: CharacterBuild

    def dispatch(self, request, *args, **kwargs):
        build = cast(CharacterBuild, self.get_object())
        user_id = getattr(request.user, 'id', None)
        if not (build.owner_id == user_id or is_campaign_dm(request.user, build.campaign)):
            return HttpResponseForbidden('You cannot edit this build.')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('characters:detail', args=[self.object.pk])

    def form_valid(self, form):
        current_build = cast(CharacterBuild, self.get_object())
        requested_status = form.cleaned_data.get(
            'status', current_build.status)

        if requested_status == CharacterBuild.Status.ACTIVE:
            validation_result = require_valid_build_for_reuse(current_build)
            if not validation_result.is_valid:
                form.add_error(
                    None,
                    'This build must pass current validation before it can be activated or reused.',
                )
                return self.form_invalid(form)

        response = super().form_valid(form)
        sync_selected_options_for_build(self.object)
        return response


class DMAllBuildsView(LoginRequiredMixin, ListView):
    model = CharacterBuild
    template_name = 'characters/dm_all_builds.html'
    campaign: Campaign

    def dispatch(self, request, *args, **kwargs):
        self.campaign = cast(Campaign, get_object_or_404(
            Campaign, pk=kwargs['campaign_pk']))
        if not is_campaign_dm(request.user, self.campaign):
            return HttpResponseForbidden('DM access required')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = campaign_builds_for_dm(self.request.user, self.campaign)
        validation_filter = self.request.GET.get('validation_status', '').upper()
        if validation_filter == CharacterBuild.ValidationStatus.STALE:
            return queryset.filter(
                Q(needs_revalidation=True) |
                Q(validation_status=CharacterBuild.ValidationStatus.STALE)
            )
        if validation_filter in CharacterBuild.ValidationStatus.values:
            return queryset.filter(validation_status=validation_filter)
        if validation_filter == 'ATTENTION':
            return builds_requiring_validation_attention(queryset)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_builds = campaign_builds_for_dm(self.request.user, self.campaign)
        context['campaign'] = self.campaign
        context['validation_summary'] = build_validation_summary(all_builds)
        context['active_validation_filter'] = self.request.GET.get(
            'validation_status', '').upper()
        return context


class NPCCreateView(CharacterBuildCreateView):
    def get_initial(self):
        initial = super().get_initial()
        initial['build_type'] = CharacterBuild.BuildType.NPC
        return initial


@login_required
def revalidate_build_view(request, pk):
    if request.method != 'POST':
        return redirect('characters:detail', pk=pk)

    build = get_object_or_404(CharacterBuild, pk=pk)
    if not can_view_build(request.user, build):
        return HttpResponseForbidden('You cannot revalidate this build.')

    result = revalidate_character_build(build)
    if result.is_valid:
        messages.success(
            request,
            'Build validated successfully and is ready for reuse.',
        )
    else:
        messages.error(
            request,
            'Build validation failed. Review the validation errors before reuse.',
        )
    return redirect('characters:detail', pk=pk)
