from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from campaigns.models import Campaign
from campaigns.permissions import can_create_npc, can_view_build, is_campaign_dm

from .forms import CharacterBuildForm
from .models import CharacterBuild
from .selectors import campaign_builds_for_dm, visible_builds_for_user
from .services import build_character_sheet_context


class PlayerDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'characters/player_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['campaigns'] = Campaign.objects.filter(memberships__user=self.request.user).distinct()
        context['builds'] = visible_builds_for_user(self.request.user)
        return context


class CharacterBuildListView(LoginRequiredMixin, ListView):
    model = CharacterBuild
    template_name = 'characters/build_list.html'

    def get_queryset(self):
        return visible_builds_for_user(self.request.user)


class CharacterBuildDetailView(LoginRequiredMixin, DetailView):
    model = CharacterBuild
    template_name = 'characters/build_detail.html'

    def dispatch(self, request, *args, **kwargs):
        build = self.get_object()
        if not can_view_build(request.user, build):
            return HttpResponseForbidden('You cannot view this build.')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sheet'] = build_character_sheet_context(self.object)
        return context


class CharacterBuildCreateView(LoginRequiredMixin, CreateView):
    model = CharacterBuild
    form_class = CharacterBuildForm
    template_name = 'characters/build_form.html'

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
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('characters:detail', args=[self.object.pk])


class CharacterBuildUpdateView(LoginRequiredMixin, UpdateView):
    model = CharacterBuild
    form_class = CharacterBuildForm
    template_name = 'characters/build_form.html'

    def dispatch(self, request, *args, **kwargs):
        build = self.get_object()
        if not (build.owner_id == request.user.id or is_campaign_dm(request.user, build.campaign)):
            return HttpResponseForbidden('You cannot edit this build.')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('characters:detail', args=[self.object.pk])


class DMAllBuildsView(LoginRequiredMixin, ListView):
    model = CharacterBuild
    template_name = 'characters/dm_all_builds.html'

    def dispatch(self, request, *args, **kwargs):
        self.campaign = get_object_or_404(Campaign, pk=kwargs['campaign_pk'])
        if not is_campaign_dm(request.user, self.campaign):
            return HttpResponseForbidden('DM access required')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return campaign_builds_for_dm(self.request.user, self.campaign)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['campaign'] = self.campaign
        return context


class NPCCreateView(CharacterBuildCreateView):
    def get_initial(self):
        initial = super().get_initial()
        initial['build_type'] = CharacterBuild.BuildType.NPC
        return initial
