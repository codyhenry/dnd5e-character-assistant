from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import SignUpForm


def signup(request):
    if request.user.is_authenticated:
        return redirect('campaigns:list')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request, 'Welcome to the guild. Your account is ready.')
            return redirect('campaigns:list')
    else:
        form = SignUpForm()

    return render(request, 'registration/signup.html', {'form': form})
