from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import FormView

from campaigns.permissions import is_campaign_member

from .forms import AICharacterPromptForm
from .services import extract_build_intent, generate_candidate_build, repair_candidate_build, retrieve_candidate_options


class AICharacterPromptView(LoginRequiredMixin, FormView):
    template_name = 'ai_builder/prompt.html'
    form_class = AICharacterPromptForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        campaign = form.cleaned_data['campaign']
        if not is_campaign_member(self.request.user, campaign):
            form.add_error('campaign', 'You must belong to the selected campaign.')
            return self.form_invalid(form)

        ruleset = campaign.active_ruleset
        if ruleset is None:
            form.add_error('campaign', 'Campaign must have an active ruleset before AI generation.')
            return self.form_invalid(form)

        intent = extract_build_intent(form.cleaned_data['prompt'])
        legal_options = retrieve_candidate_options(intent, ruleset)
        candidate = generate_candidate_build(intent, legal_options, ruleset)

        if not legal_options:
            candidate = repair_candidate_build(candidate, ['No legal options found'], legal_options)

        context = self.get_context_data(form=form, intent=intent, candidate_build=candidate, legal_options=legal_options)
        return self.render_to_response(context)
