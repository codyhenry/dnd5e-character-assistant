from django import forms


class AICharacterPromptForm(forms.Form):
    campaign = forms.ModelChoiceField(queryset=None)
    prompt = forms.CharField(widget=forms.Textarea, label='Character concept')

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['campaign'].queryset = user.campaigns.all()
