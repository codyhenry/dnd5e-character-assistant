from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class SignUpViewTests(TestCase):
    def test_signup_page_renders(self):
        response = self.client.get(reverse('signup'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/signup.html')

    def test_signup_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse('signup'),
            {
                'username': 'newhero',
                'email': 'newhero@example.com',
                'password1': 'ComplexPass123!',
                'password2': 'ComplexPass123!',
            },
        )

        self.assertRedirects(response, reverse('campaigns:list'))
        self.assertTrue(User.objects.filter(username='newhero').exists())
        self.assertTrue(response.wsgi_request.user.is_authenticated)
