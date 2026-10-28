from unittest.mock import patch

from django.test import override_settings

from .models import Comment
from .notifications import notify_new_comment
from .test_helpers import TravelTestCase


class NotificationTests(TravelTestCase):
    def setUp(self):
        super().setUp()
        self.comment = Comment.objects.create(tour=self.tour, user=self.user,
                                              subject='Question', text='Hello')

    @override_settings(COMMENT_NOTIFICATION_EMAIL='')
    @patch('tours.notifications.send_mail')
    def test_no_recipient_skips_sending(self, send):
        notify_new_comment(self.comment, 'http://testserver/tours/mountains/')
        send.assert_not_called()

    @override_settings(COMMENT_NOTIFICATION_EMAIL='moderator@example.com')
    def test_transport_and_configuration_errors_are_logged(self):
        for error in (OSError('Offline'), ValueError('Invalid configuration')):
            with self.subTest(error=type(error).__name__):
                with patch('tours.notifications.send_mail', side_effect=error):
                    with self.assertLogs('tours.notifications', level='ERROR'):
                        notify_new_comment(self.comment, 'http://testserver/tours/mountains/')
                self.assertTrue(Comment.objects.filter(pk=self.comment.pk).exists())
