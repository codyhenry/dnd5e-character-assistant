from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from .forms import DNDOptionForm
from .models import DNDOption


class DNDOptionListView(LoginRequiredMixin, ListView):
    model = DNDOption
    template_name = 'dnd_options/option_list.html'


class DNDOptionCreateView(LoginRequiredMixin, CreateView):
    model = DNDOption
    form_class = DNDOptionForm
    template_name = 'dnd_options/option_form.html'
    success_url = reverse_lazy('dnd_options:list')
