from smtplib import SMTPException
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import Comment, Region, Tour


@override_settings(
    MAILERS={'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}},
    COMMENT_NOTIFICATION_EMAIL='moderator@example.com',
)
class Lesson19Tests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user('reader19', password='safe-password-123')
        self.tour = Tour.objects.create(
            name='Unique mountain trip', slug='lesson19', description='Description',
            region=Region.objects.create(name='Region'), duration_days=1, price=1000,
            route='Route',
        )
        self.detail = reverse('tours:tour_detail', args=[self.tour.slug])
        self.catalog = reverse('tours:tour_list')

    def test_comment_sends_one_email_after_commit(self):
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(self.detail, {'subject': 'Question', 'text': 'Hello'})
            self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['moderator@example.com'])
        for value in ('Unique mountain trip', 'reader19', 'Question', 'Hello', self.detail):
            self.assertIn(value, mail.outbox[0].body)
        self.client.get(self.detail)
        self.assertEqual(len(mail.outbox), 1)

    def test_invalid_or_anonymous_comment_sends_no_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.detail, {'subject': 'Question', 'text': 'Hello'})
            self.client.force_login(self.user)
            self.client.post(self.detail, {'subject': '', 'text': ''})
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(Comment.objects.exists())

    def test_mail_failure_preserves_comment(self):
        self.client.force_login(self.user)
        with patch('tours.notifications.send_mail', side_effect=SMTPException('Offline')):
            with self.assertLogs('tours.notifications', level='ERROR'):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(self.detail, {'subject': 'Question', 'text': 'Hello'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Comment.objects.count(), 1)

    def test_language_switch_and_translated_forms(self):
        self.assertContains(self.client.get(reverse('home')), 'Добро пожаловать')
        response = self.client.post(reverse('set_language'), {'language': 'en', 'next': self.detail})
        self.assertRedirects(response, self.detail)
        self.assertEqual(self.client.cookies['django_language'].value, 'en')
        self.assertContains(self.client.get(reverse('home')), 'Welcome to Kyrgyz Tur!')
        self.assertContains(self.client.get(reverse('register')), 'Create account')
        self.client.force_login(self.user)
        self.assertContains(self.client.get(self.detail), 'Comment subject')
        self.assertContains(self.client.get(reverse('bookings:profile')), 'Maximum budget')
        self.assertContains(self.client.get(reverse('tours:tour_recommend')), 'Budget per person')
        self.client.post(reverse('set_language'), {'language': 'ru', 'next': '/'})
        self.assertContains(self.client.get(reverse('home')), 'Добро пожаловать')

    def test_catalog_cache_hit_and_filter_language_isolation(self):
        with CaptureQueriesContext(connection) as cold:
            self.assertContains(self.client.get(self.catalog), self.tour.name)
        with CaptureQueriesContext(connection) as warm:
            self.assertContains(self.client.get(self.catalog), self.tour.name)
        self.assertLess(len(warm), len(cold))
        self.assertNotContains(self.client.get(self.catalog, {'search': 'absent'}), self.tour.name)
        self.client.post(reverse('set_language'), {'language': 'en', 'next': self.catalog})
        self.assertContains(self.client.get(self.catalog), 'Tour catalogue')

    def test_catalog_cache_does_not_share_account_navigation(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(self.catalog), 'reader19')
        self.client.logout()
        self.assertNotContains(self.client.get(self.catalog), 'reader19')
        self.assertContains(self.client.get(self.catalog), reverse('login'))

    def test_catalog_cache_refresh(self):
        self.client.get(self.catalog)
        Tour.objects.filter(pk=self.tour.pk).update(name='Updated trip')
        self.assertNotContains(self.client.get(self.catalog), 'Updated trip')
        cache.clear()
        self.assertContains(self.client.get(self.catalog), 'Updated trip')

    def test_login_logout_and_private_page(self):
        response = self.client.get(reverse('bookings:booking_list'))
        self.assertEqual(response.status_code, 302)
        response = self.client.post(reverse('login'), {'username': 'reader19', 'password': 'safe-password-123'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(reverse('bookings:booking_list')).status_code, 200)
        self.client.post(reverse('logout'))
        self.assertEqual(self.client.get(reverse('bookings:booking_list')).status_code, 302)
