from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class RegistrationTests(TestCase):
    def test_successful_registration_logs_user_in(self):
        response = self.client.post(reverse('register'), {
            'username': 'newtraveler', 'password1': 'Travel-unique-7294',
            'password2': 'Travel-unique-7294',
        })
        self.assertRedirects(response, reverse('bookings:booking_list'))
        user = User.objects.get(username='newtraveler')
        self.assertTrue(user.check_password('Travel-unique-7294'))
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_invalid_registration_does_not_create_user_or_session(self):
        User.objects.create_user('existing')
        for username, first, second, field in [
            ('existing', 'Travel-unique-7294', 'Travel-unique-7294', 'username'),
            ('new', 'Travel-unique-7294', 'Different-9274', 'password2'),
            ('new', '123', '123', 'password2'),
            ('', 'Travel-unique-7294', 'Travel-unique-7294', 'username'),
        ]:
            with self.subTest(username=username, field=field):
                response = self.client.post(reverse('register'), {
                    'username': username, 'password1': first, 'password2': second,
                })
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context['form'].errors)
                self.assertEqual(User.objects.count(), 1)
                self.assertNotIn('_auth_user_id', self.client.session)

    def test_authenticated_user_redirected_without_new_registration(self):
        user = User.objects.create_user('existing')
        self.client.force_login(user)
        for method in (self.client.get, self.client.post):
            self.assertRedirects(method(reverse('register')), reverse('bookings:booking_list'))
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_login_remains_anonymous(self):
        User.objects.create_user('existing', password='Travel-unique-7294')
        response = self.client.post(reverse('login'), {'username': 'existing', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertNotIn('_auth_user_id', self.client.session)
