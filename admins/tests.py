from django.test import Client, TestCase
from django.urls import reverse

from home.models import userProfile


class AdminAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = userProfile.objects.create(
            name='Demo User',
            email='demo@example.com',
            password='Password1',
            confirm_password='Password1',
            mobile='9123456789',
            status='waiting',
        )

    def test_activate_user_without_admin_session_redirects_to_admin_login(self):
        response = self.client.get(reverse('activate_user', args=[self.user.id]))

        self.assertRedirects(response, reverse('adminlogin'))

    def test_register_users_view_requires_admin_session(self):
        response = self.client.get(reverse('RegisterUsersView'))

        self.assertRedirects(response, reverse('adminlogin'))
