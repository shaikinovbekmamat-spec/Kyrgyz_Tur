from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from .models import Region, Review, TourDate
from .test_helpers import TravelTestCase


class TourModelTests(TravelTestCase):
    def test_available_dates_include_today_but_exclude_past_and_sold_out(self):
        today = timezone.localdate()
        current = TourDate.objects.create(tour=self.tour, date=today, available_spots=1)
        TourDate.objects.create(tour=self.tour, date=today - timedelta(days=1), available_spots=2)
        TourDate.objects.create(tour=self.tour, date=today + timedelta(days=1), available_spots=0)
        self.assertQuerySetEqual(self.tour.get_available_dates(), [current, self.date])

    def test_final_price_is_rounded_to_cents(self):
        self.tour.price = Decimal('1000.01')
        self.date.price_modifier = Decimal('1.23')
        self.assertEqual(self.date.get_final_price(), Decimal('1230.01'))

    def test_end_date_cannot_precede_start(self):
        self.date.end_date = self.date.date - timedelta(days=1)
        with self.assertRaises(ValidationError) as error:
            self.date.full_clean()
        self.assertIn('end_date', error.exception.message_dict)
        self.date.end_date = self.date.date
        self.date.full_clean()

    def test_invalid_model_values(self):
        for field, value in (('duration_days', 0), ('price', Decimal('-1'))):
            with self.subTest(field=field):
                original = getattr(self.tour, field)
                setattr(self.tour, field, value)
                with self.assertRaises(ValidationError) as error:
                    self.tour.full_clean()
                self.assertIn(field, error.exception.message_dict)
                setattr(self.tour, field, original)
        self.date.price_modifier = Decimal('0')
        with self.assertRaises(ValidationError):
            self.date.full_clean()

    def test_duplicate_date_and_review_are_invalid(self):
        duplicate = TourDate(tour=self.tour, date=self.date.date, available_spots=1)
        with self.assertRaises(ValidationError):
            duplicate.full_clean()
        Review.objects.create(tour=self.tour, user=self.user, rating=5, comment='Great')
        with self.assertRaises(ValidationError):
            Review(tour=self.tour, user=self.user, rating=4, comment='Again').full_clean()


class CatalogTests(TravelTestCase):
    def test_filters_select_expected_tours(self):
        other_region = Region.objects.create(name='Osh')
        self.make_tour('city', region=other_region, category=None, duration_days=1,
                       price=2000, difficulty='hard', description='Museum', route='City')
        cases = [({'region': self.region.pk}, [self.tour]),
                 ({'category': self.category.pk}, [self.tour]),
                 ({'min_price': 1000, 'max_price': 1000}, [self.tour]),
                 ({'duration': 2, 'difficulty': 'medium'}, [self.tour]),
                 ({'search': 'mountains'}, [self.tour]),
                 ({'search': 'walk'}, [self.tour]),
                 ({'search': 'Naryn'}, [self.tour]),
                 ({'search': 'missing'}, [])]
        for params, expected in cases:
            with self.subTest(params=params):
                response = self.client.get(reverse('tours:tour_list'), params)
                self.assertEqual(list(response.context['page_obj']), expected)

    def test_inactive_tours_are_hidden_and_detail_returns_404(self):
        self.tour.is_active = False
        self.tour.save()
        response = self.client.get(reverse('tours:tour_list'))
        self.assertEqual(list(response.context['page_obj']), [])
        for slug in (self.tour.slug, 'missing'):
            self.assertEqual(self.client.get(reverse('tours:tour_detail', args=[slug])).status_code, 404)

    def test_sorting_and_tie_breaking(self):
        cheap = self.make_tour('cheap', price=500, duration_days=1)
        equal = self.make_tour('equal')
        for sort, expected in [('price', [cheap, self.tour, equal]),
                               ('-price', [self.tour, equal, cheap]),
                               ('duration_days', [cheap, self.tour, equal])]:
            with self.subTest(sort=sort):
                response = self.client.get(reverse('tours:tour_list'), {'sort': sort})
                self.assertEqual(list(response.context['page_obj']), expected)

    def test_pagination_and_filter_query(self):
        for number in range(13):
            self.make_tour(f'trip-{number}')
        for page, expected_number, count in [('bad', 1, 12), ('999', 2, 2), ('2', 2, 2)]:
            with self.subTest(page=page):
                response = self.client.get(reverse('tours:tour_list'), {'page': page, 'duration': 2})
                self.assertEqual(response.context['page_obj'].number, expected_number)
                self.assertEqual(len(response.context['page_obj']), count)
                self.assertEqual(response.context['filter_query'], 'duration=2')

    def test_detail_rating_and_similar_tours(self):
        similar = self.make_tour('similar')
        self.make_tour('inactive', is_active=False)
        self.make_tour('elsewhere', region=Region.objects.create(name='Elsewhere'))
        Review.objects.create(tour=self.tour, user=self.user, rating=5, comment='Great')
        Review.objects.create(tour=self.tour, user=self.other, rating=3, comment='Fine')
        response = self.client.get(reverse('tours:tour_detail', args=[self.tour.slug]))
        self.assertEqual(response.context['avg_rating'], 4)
        self.assertQuerySetEqual(response.context['similar_tours'], [similar])
