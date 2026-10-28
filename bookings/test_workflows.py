from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from tours.test_helpers import TravelTestCase
from .forms import ProfileForm
from .models import Booking, UserProfile


class BookingModelTests(TravelTestCase):
    def test_confirm_exact_capacity_today_and_record_timestamp(self):
        self.date.date = timezone.localdate()
        self.date.save()
        booking = self.make_booking(participants_count=3)
        self.assertTrue(booking.confirm())
        self.assertEqual(booking.status, 'confirmed')
        self.assertIsNotNone(booking.confirmed_at)
        self.date.refresh_from_db()
        self.assertEqual(self.date.available_spots, 0)

    def test_inactive_tour_cannot_be_confirmed(self):
        self.tour.is_active = False
        self.tour.save()
        self.assertFalse(self.make_booking().confirm())
        self.date.refresh_from_db()
        self.assertEqual(self.date.available_spots, 3)

    def test_mismatched_tour_date_is_rejected(self):
        booking = self.make_booking(tour=self.make_tour('another'))
        with self.assertRaises(ValidationError) as error:
            booking.clean()
        self.assertIn('tour_date', error.exception.message_dict)
        self.assertFalse(booking.confirm())

    def test_zero_participants_cannot_be_confirmed(self):
        booking = self.make_booking(participants_count=0)
        self.assertFalse(booking.confirm())
        with self.assertRaises(ValidationError):
            booking.full_clean()

    def test_terminal_statuses_cannot_be_confirmed_or_cancelled(self):
        for status in ('cancelled', 'completed'):
            with self.subTest(status=status):
                booking = self.make_booking(status=status)
                self.assertFalse(booking.confirm())
                self.assertFalse(booking.cancel())
                booking.refresh_from_db()
                self.assertEqual(booking.status, status)
        self.date.refresh_from_db()
        self.assertEqual(self.date.available_spots, 3)


class BookingViewTests(TravelTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url = reverse('bookings:create_booking', args=[self.tour.pk, self.date.pk])
        self.data = dict(participants_count=2, contact_name='Traveler',
                         contact_phone='123', contact_email='test@example.com')

    def test_private_pages_require_login(self):
        booking = self.make_booking()
        urls = [self.url, reverse('bookings:booking_list'), reverse('bookings:profile')]
        urls += [reverse('bookings:' + name, args=[booking.pk])
                 for name in ('booking_detail', 'cancel_booking')]
        self.client.logout()
        for url in urls:
            for method in (self.client.get, self.client.post):
                with self.subTest(url=url, method=method.__name__):
                    self.assertRedirects(method(url), reverse('login') + '?next=' + url)

    def test_create_ignores_forged_owner_status_and_price(self):
        response = self.client.post(self.url, {
            **self.data, 'user': self.other.pk, 'status': 'confirmed', 'total_price': '1',
        })
        booking = Booking.objects.get()
        self.assertRedirects(response, reverse('bookings:booking_detail', args=[booking.pk]))
        self.assertEqual(booking.user, self.user)
        self.assertEqual(booking.status, 'pending')
        self.assertEqual(booking.total_price, Decimal('2000.00'))
        self.date.refresh_from_db()
        self.assertEqual(self.date.available_spots, 3)

    def test_unavailable_dates_reject_get_and_post(self):
        for days, spots in ((-1, 3), (7, 0)):
            self.date.date = timezone.localdate() + timedelta(days=days)
            self.date.available_spots = spots
            self.date.save()
            for method in (self.client.get, self.client.post):
                with self.subTest(days=days, spots=spots, method=method.__name__):
                    self.assertRedirects(method(self.url, self.data),
                                         reverse('tours:tour_detail', args=[self.tour.slug]))
        self.assertFalse(Booking.objects.exists())

    def test_mismatched_date_and_inactive_tour_return_404(self):
        other = self.make_tour('another')
        url = reverse('bookings:create_booking', args=[other.pk, self.date.pk])
        self.assertEqual(self.client.post(url, self.data).status_code, 404)
        self.tour.is_active = False
        self.tour.save()
        self.assertEqual(self.client.post(self.url, self.data).status_code, 404)
        self.assertFalse(Booking.objects.exists())

    def test_get_prefills_contact_without_creating_booking(self):
        form = self.client.get(self.url).context['form']
        self.assertEqual(form.initial['contact_name'], self.user.username)
        self.assertEqual(form.initial['contact_email'], self.user.email)
        self.assertFalse(Booking.objects.exists())

    def test_invalid_contacts_do_not_create_booking(self):
        for field, value in (('contact_name', ''), ('contact_phone', ''),
                             ('contact_email', 'invalid')):
            with self.subTest(field=field):
                response = self.client.post(self.url, {**self.data, field: value})
                self.assertIn(field, response.context['form'].errors)
        self.assertFalse(Booking.objects.exists())

    def test_list_contains_only_current_users_bookings(self):
        own = self.make_booking()
        self.make_booking(user=self.other)
        response = self.client.get(reverse('bookings:booking_list'))
        self.assertQuerySetEqual(response.context['bookings'], [own])

    def test_cancellation_requires_post_and_returns_seats_once(self):
        booking = self.make_booking()
        booking.confirm()
        url = reverse('bookings:cancel_booking', args=[booking.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'confirmed')
        for _ in range(2):
            self.assertRedirects(self.client.post(url), reverse('bookings:booking_list'))
        booking.refresh_from_db()
        self.date.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')
        self.assertEqual(self.date.available_spots, 3)

    def test_cannot_cancel_someone_elses_booking(self):
        booking = self.make_booking(user=self.other)
        response = self.client.post(reverse('bookings:cancel_booking', args=[booking.pk]))
        self.assertEqual(response.status_code, 404)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'pending')


class ProfileTests(TravelTestCase):
    def test_budget_and_duration_validation(self):
        for data, field in [({'preferred_budget_min': -1}, 'preferred_budget_min'),
                            ({'preferred_budget_max': -1}, 'preferred_budget_max'),
                            ({'preferred_budget_min': 100, 'preferred_budget_max': 99}, 'preferred_budget_max'),
                            ({'preferred_duration_days': 0}, 'preferred_duration_days')]:
            with self.subTest(data=data):
                form = ProfileForm(data=data)
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_optional_preferences_and_equal_zero_budgets_are_valid(self):
        for data in ({}, {'preferred_budget_min': 0, 'preferred_budget_max': 0}):
            self.assertTrue(ProfileForm(data=data).is_valid())

    def test_profile_is_created_once_and_updates_only_owner(self):
        other = UserProfile.objects.create(user=self.other, interests='Unchanged')
        self.client.force_login(self.user)
        url = reverse('bookings:profile')
        self.client.get(url)
        self.client.get(url)
        response = self.client.post(url, {'user': self.other.pk, 'phone': '123',
            'preferred_budget_min': '100', 'preferred_budget_max': '2000',
            'preferred_duration_days': 2, 'interests': 'Mountains'})
        self.assertRedirects(response, url)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.preferred_budget_max, Decimal('2000'))
        self.assertEqual(profile.interests, 'Mountains')
        other.refresh_from_db()
        self.assertEqual(other.interests, 'Unchanged')
        self.assertEqual(UserProfile.objects.count(), 2)
