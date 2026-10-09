from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from tours.models import Region, Tour, TourDate
from .models import Booking


class MVPTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('traveler', password='travel-pass-123')
        self.tour = Tour.objects.create(name='Горный тур', slug='mountains', description='Горы',
            region=Region.objects.create(name='Сон-Куль'), duration_days=2, price=4500, route='Бишкек → Сон-Куль')
        self.date = TourDate.objects.create(tour=self.tour, date=timezone.localdate()+timedelta(days=7), available_spots=3)
        self.client.force_login(self.user)

    def booking(self, count=2):
        return Booking.objects.create(user=self.user, tour=self.tour, tour_date=self.date,
            participants_count=count, total_price=Decimal(4500)*count, contact_name='Тест',
            contact_phone='+996555123456', contact_email='test@example.com')

    def test_confirm_checks_current_capacity(self):
        first, second = self.booking(), self.booking()
        self.assertTrue(first.confirm())
        self.assertFalse(second.confirm())
        self.date.refresh_from_db()
        self.assertEqual(self.date.available_spots, 1)
        second.refresh_from_db()
        self.assertEqual(second.status, 'pending')

    def test_stale_instances_do_not_double_confirm_or_cancel(self):
        booking = self.booking()
        stale = Booking.objects.get(pk=booking.pk)
        self.assertTrue(booking.confirm())
        self.assertFalse(stale.confirm())
        self.assertTrue(stale.cancel())
        self.assertFalse(booking.cancel())
        self.date.refresh_from_db()
        self.assertEqual(self.date.available_spots, 3)

    def test_pending_cancel_does_not_add_seats(self):
        self.assertTrue(self.booking().cancel())
        self.date.refresh_from_db()
        self.assertEqual(self.date.available_spots, 3)

    def test_invalid_counts(self):
        url = reverse('bookings:create_booking', args=[self.tour.pk, self.date.pk])
        for count in ('0', '-1', 'invalid', '4'):
            response = self.client.post(url, {'participants_count': count, 'contact_name': 'Тест',
                'contact_phone': '123', 'contact_email': 'test@example.com'})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        self.assertEqual(Booking.objects.count(), 0)

    def test_valid_request_price_and_pages(self):
        self.date.price_modifier = Decimal('1.20')
        self.date.save()
        response = self.client.post(reverse('bookings:create_booking', args=[self.tour.pk, self.date.pk]),
            {'participants_count': '2', 'contact_name': 'Тест', 'contact_phone': '123', 'contact_email': 'test@example.com'})
        booking = Booking.objects.get()
        self.assertEqual(booking.total_price, Decimal('10800'))
        self.assertEqual(booking.status, 'pending')
        self.assertRedirects(response, reverse('bookings:booking_detail', args=[booking.pk]))
        for name in ('booking_list', 'profile'):
            self.assertEqual(self.client.get(reverse('bookings:'+name)).status_code, 200)
        self.assertEqual(self.client.get(reverse('bookings:cancel_booking', args=[booking.pk])).status_code, 200)

    def test_other_users_cannot_access_booking(self):
        booking = self.booking()
        self.client.force_login(User.objects.create_user('other'))
        for name in ('booking_detail', 'cancel_booking'):
            self.assertEqual(self.client.get(reverse('bookings:'+name, args=[booking.pk])).status_code, 404)

    def test_past_date_cannot_be_confirmed(self):
        self.date.date = timezone.localdate()-timedelta(days=1)
        self.date.save()
        self.assertFalse(self.booking().confirm())

    def test_profile_invalid_data(self):
        response = self.client.post(reverse('bookings:profile'), {'preferred_budget_min': '-1', 'preferred_duration_days': '0'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)

    def test_registration_login_logout(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('login')).status_code, 200)
        self.assertEqual(self.client.get(reverse('register')).status_code, 200)
        response = self.client.post(reverse('register'), {'username': 'newtraveler',
            'password1': 'secure-travel-9281', 'password2': 'secure-travel-9281'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newtraveler').exists())
        self.assertEqual(self.client.post(reverse('logout')).status_code, 302)

    def test_catalog_detail_and_invalid_filters(self):
        for params in ({}, {'sort': 'unknown'}, {'region': 'abc', 'max_price': 'NaN', 'duration': '-1'}):
            self.assertEqual(self.client.get(reverse('tours:tour_list'), params).status_code, 200)
        self.assertEqual(self.client.get(reverse('tours:tour_detail', args=[self.tour.slug])).status_code, 200)

    def test_recommendation_uses_date_price(self):
        self.date.price_modifier = Decimal('1.20')
        self.date.save()
        response = self.client.post(reverse('tours:tour_recommend'), {'budget': '5000', 'duration': '2', 'interests': 'люблю горы'})
        self.assertEqual(response.context['scored_tours'], [])
        self.date.price_modifier = Decimal('1')
        self.date.save()
        response = self.client.post(reverse('tours:tour_recommend'), {'budget': '5000', 'duration': '2', 'interests': 'люблю горы'})
        self.assertEqual(response.context['scored_tours'][0]['match_percentage'], 100)

    def test_invalid_recommendation(self):
        response = self.client.post(reverse('tours:tour_recommend'), {'budget': 'bad', 'duration': 'no'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)

    def test_admin_pages_and_confirmation(self):
        admin = User.objects.create_superuser('admin', 'admin@example.com', 'admin-pass-123')
        self.client.force_login(admin)
        booking = self.booking()
        for url in (reverse('admin:bookings_booking_change', args=[booking.pk]),
                    reverse('admin:tours_tourdate_changelist')):
            self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(reverse('admin:bookings_booking_changelist'), {
            'action': 'confirm_bookings', '_selected_action': [booking.pk],
        })
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'confirmed')

    def test_demo_command_is_idempotent(self):
        from django.core.management import call_command
        from io import StringIO
        call_command('seed_demo', stdout=StringIO())
        counts = (Tour.objects.count(), TourDate.objects.count())
        call_command('seed_demo', stdout=StringIO())
        self.assertEqual(counts, (Tour.objects.count(), TourDate.objects.count()))
