"""Shared database fixtures with explicit defaults for business scenarios."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from bookings.models import Booking
from tours.models import Region, Tour, TourCategory, TourDate


class TravelTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('traveler', email='test@example.com')
        cls.other = User.objects.create_user('other')
        cls.region = Region.objects.create(name='Naryn')
        cls.category = TourCategory.objects.create(name='Hiking')
        cls.tour = cls.make_tour('mountains')
        cls.date = TourDate.objects.create(
            tour=cls.tour, date=timezone.localdate() + timedelta(days=7),
            available_spots=3,
        )

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    @classmethod
    def make_tour(cls, slug, **changes):
        data = dict(name=slug, slug=slug, description='Mountain walk',
                    region=cls.region, category=cls.category, duration_days=2,
                    price=Decimal('1000.00'), route='Bishkek to Naryn')
        data.update(changes)
        return Tour.objects.create(**data)

    def make_booking(self, **changes):
        data = dict(user=self.user, tour=self.tour, tour_date=self.date,
                    participants_count=2, total_price=Decimal('2000.00'),
                    contact_name='Traveler', contact_phone='+996555123456',
                    contact_email='test@example.com')
        data.update(changes)
        return Booking.objects.create(**data)
