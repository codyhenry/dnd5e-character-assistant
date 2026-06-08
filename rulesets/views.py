from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, UpdateView
from typing import cast

from campaigns.models import Campaign
from campaigns.permissions import can_edit_ruleset, is_campaign_member
from characters.services import mark_builds_stale_for_ruleset

from .forms import RulesetForm
from .models import Ruleset, RulesetBannedOption
from .option_forms import RulesetBannedOptionForm

RULESET_OPTION_RESTRICTION_STALE_REASON = (
    'One or more ruleset option restrictions changed after this character was last validated.'
)


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
        can_manage = can_edit_ruleset(self.request.user, self.object.campaign)
        context['can_view_hidden_guidance'] = can_manage
        context['can_manage_option_restrictions'] = can_manage
        context['option_restriction_form'] = kwargs.get(
            'option_restriction_form'
        ) or RulesetBannedOptionForm(ruleset=self.object)
        context['option_restrictions'] = self.object.banned_options.select_related(
            'banned_option', 'banned_character_build'
        ).order_by('banned_option__option_type', 'banned_option__name', 'created_at')
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


@login_required
@require_POST
def add_option_restriction_view(request, pk):
    ruleset = get_object_or_404(Ruleset, pk=pk)
    if not can_edit_ruleset(request.user, ruleset.campaign):
        return HttpResponseForbidden('DM access required')

    form = RulesetBannedOptionForm(request.POST, ruleset=ruleset)
    if form.is_valid():
        form.save()
        mark_builds_stale_for_ruleset(
            ruleset,
            reason=RULESET_OPTION_RESTRICTION_STALE_REASON,
        )
        messages.success(request, 'Ruleset option restriction added.')
        return redirect('rulesets:detail', pk=ruleset.pk)

    detail_view = RulesetDetailView()
    detail_view.request = request
    detail_view.object = ruleset
    context = detail_view.get_context_data(option_restriction_form=form)
    return detail_view.render_to_response(context)


@login_required
@require_POST
def remove_option_restriction_view(request, pk, restriction_pk):
    ruleset = get_object_or_404(Ruleset, pk=pk)
    if not can_edit_ruleset(request.user, ruleset.campaign):
        return HttpResponseForbidden('DM access required')

    restriction = get_object_or_404(
        RulesetBannedOption,
        pk=restriction_pk,
        ruleset=ruleset,
    )
    restriction.delete()
    mark_builds_stale_for_ruleset(
        ruleset,
        reason=RULESET_OPTION_RESTRICTION_STALE_REASON,
    )
    messages.success(request, 'Ruleset option restriction removed.')
    return redirect('rulesets:detail', pk=ruleset.pk)
