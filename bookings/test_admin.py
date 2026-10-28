from datetime import timedelta

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from tours.models import TourDate
from tours.test_helpers import TravelTestCase


class BookingAdminTests(TravelTestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'password')
        self.client.force_login(self.admin)
        self.url = reverse('admin:bookings_booking_changelist')

    def action(self, action, bookings):
        response = self.client.post(self.url, {
            'action': action, '_selected_action': [booking.pk for booking in bookings],
        })
        self.assertEqual(response.status_code, 302)
        for booking in bookings:
            booking.refresh_from_db()

    def test_bulk_confirm_cannot_overbook(self):
        bookings = [self.make_booking(), self.make_booking()]
        self.action('confirm_bookings', bookings)
        self.assertCountEqual([booking.status for booking in bookings], ['pending', 'confirmed'])
        self.date.refresh_from_db()
        self.assertEqual(self.date.available_spots, 1)

    def test_bulk_cancel_restores_only_reserved_seats(self):
        confirmed = self.make_booking()
        confirmed.confirm()
        bookings = [confirmed, self.make_booking(), self.make_booking(status='completed')]
        self.action('cancel_bookings', bookings)
        self.action('cancel_bookings', bookings)
        self.assertEqual([booking.status for booking in bookings], ['cancelled', 'cancelled', 'completed'])
        self.date.refresh_from_db()
        self.assertEqual(self.date.available_spots, 3)

    def test_complete_only_confirmed_trips_that_have_ended(self):
        today = timezone.localdate()
        cases = [(-5, -1, 'confirmed', 'completed'),
                 (-4, None, 'confirmed', 'completed'),
                 (-3, 0, 'confirmed', 'confirmed'),
                 (-2, 1, 'confirmed', 'confirmed'),
                 (0, None, 'confirmed', 'confirmed'),
                 (-6, None, 'pending', 'pending'),
                 (-7, None, 'cancelled', 'cancelled')]
        bookings = []
        for start, end, status, expected in cases:
            date = TourDate.objects.create(tour=self.tour, date=today + timedelta(days=start),
                end_date=None if end is None else today + timedelta(days=end), available_spots=1)
            bookings.append(self.make_booking(tour_date=date, status=status))
        self.action('complete_bookings', bookings)
        self.assertEqual([booking.status for booking in bookings], [case[3] for case in cases])
        self.assertTrue(all(booking.tour_date.available_spots == 1 for booking in bookings))

    def test_admin_cannot_add_or_delete_booking(self):
        booking = self.make_booking()
        self.assertEqual(self.client.get(reverse('admin:bookings_booking_add')).status_code, 403)
        self.assertEqual(self.client.post(reverse('admin:bookings_booking_delete', args=[booking.pk]),
                                          {'post': 'yes'}).status_code, 403)

    def test_regular_user_cannot_run_admin_actions(self):
        self.client.force_login(self.user)
        booking = self.make_booking()
        response = self.client.post(self.url, {'action': 'confirm_bookings', '_selected_action': [booking.pk]})
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'pending')
