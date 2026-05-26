from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from .forms import CampaignForm, CampaignMembershipForm
from .models import Campaign
from .permissions import is_campaign_dm, is_campaign_member
from .services import add_or_update_membership


class CampaignListView(LoginRequiredMixin, ListView):
    model = Campaign
    template_name = 'campaigns/campaign_list.html'

    def get_queryset(self):
        return Campaign.objects.filter(memberships__user=self.request.user).distinct()


class DMCampaignDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'campaigns/dm_dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        self.campaign = get_object_or_404(Campaign, pk=kwargs['pk'])
        if not is_campaign_dm(request.user, self.campaign):
            return HttpResponseForbidden('DM access required')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['campaign'] = self.campaign
        context['builds'] = self.campaign.character_builds.select_related('owner')
        return context


class CampaignDetailView(LoginRequiredMixin, DetailView):
    model = Campaign
    template_name = 'campaigns/campaign_detail.html'

    def dispatch(self, request, *args, **kwargs):
        campaign = self.get_object()
        if not is_campaign_member(request.user, campaign):
            return HttpResponseForbidden('Campaign membership required')
        return super().dispatch(request, *args, **kwargs)


class CampaignCreateView(LoginRequiredMixin, CreateView):
    model = Campaign
    form_class = CampaignForm
    template_name = 'campaigns/campaign_form.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        add_or_update_membership(campaign=self.object, user=self.request.user, role='DM')
        return response

    def get_success_url(self):
        return reverse('campaigns:detail', args=[self.object.pk])


class CampaignUpdateView(LoginRequiredMixin, UpdateView):
    model = Campaign
    form_class = CampaignForm
    template_name = 'campaigns/campaign_form.html'

    def dispatch(self, request, *args, **kwargs):
        campaign = self.get_object()
        if not is_campaign_dm(request.user, campaign):
            return HttpResponseForbidden('DM access required')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('campaigns:detail', args=[self.object.pk])


class CampaignMembershipManageView(LoginRequiredMixin, DetailView):
    model = Campaign
    template_name = 'campaigns/manage_members.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not is_campaign_dm(request.user, self.object):
            return HttpResponseForbidden('DM access required')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['membership_form'] = CampaignMembershipForm()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not is_campaign_dm(request.user, self.object):
            return HttpResponseForbidden('DM access required')
        form = CampaignMembershipForm(request.POST)
        if form.is_valid():
            add_or_update_membership(
                campaign=self.object,
                user=form.cleaned_data['user'],
                role=form.cleaned_data['role'],
            )
        return redirect('campaigns:manage_members', pk=self.object.pk)
