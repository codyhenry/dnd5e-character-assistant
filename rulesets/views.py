from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DetailView, UpdateView
from typing import cast

from campaigns.models import Campaign
from campaigns.permissions import can_edit_ruleset, is_campaign_member

from .forms import RulesetForm
from .models import Ruleset


class RulesetDetailView(LoginRequiredMixin, DetailView):
    model = Ruleset
    template_name = 'rulesets/ruleset_detail.html'
    object: Ruleset

    def dispatch(self, request, *args, **kwargs):
        ruleset = cast(Ruleset, self.get_object())
        if not is_campaign_member(request.user, ruleset.campaign):
            return HttpResponseForbidden('Campaign membership required')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_view_hidden_guidance'] = can_edit_ruleset(
            self.request.user, self.object.campaign)
        return context


class RulesetCreateView(LoginRequiredMixin, CreateView):
    model = Ruleset
    form_class = RulesetForm
    template_name = 'rulesets/ruleset_form.html'
    object: Ruleset

    def dispatch(self, request, *args, **kwargs):
        self.campaign = cast(Campaign, get_object_or_404(
            Campaign, pk=kwargs['campaign_pk']))
        if not can_edit_ruleset(request.user, self.campaign):
            return HttpResponseForbidden('DM access required')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.campaign = self.campaign
        response = super().form_valid(form)
        self.campaign.active_ruleset = self.object
        self.campaign.save(update_fields=['active_ruleset'])
        return response

    def get_success_url(self):
        return reverse('rulesets:detail', args=[self.object.pk])


class RulesetUpdateView(LoginRequiredMixin, UpdateView):
    model = Ruleset
    form_class = RulesetForm
    template_name = 'rulesets/ruleset_form.html'
    object: Ruleset

    def dispatch(self, request, *args, **kwargs):
        ruleset = cast(Ruleset, self.get_object())
        if not can_edit_ruleset(request.user, ruleset.campaign):
            return HttpResponseForbidden('DM access required')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('rulesets:detail', args=[self.object.pk])
