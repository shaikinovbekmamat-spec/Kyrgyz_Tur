from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from bookings.models import UserProfile
from .models import Review, TourDate
from .test_helpers import TravelTestCase


class RecommendationTests(TravelTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse('tours:tour_recommend')
        self.client.force_login(self.user)

    def results(self, **data):
        return self.client.post(self.url, {'budget': 2000, **data}).context['scored_tours']

    def test_login_required(self):
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), reverse('login') + '?next=' + self.url)

    def test_profile_preferences_prefill_form(self):
        UserProfile.objects.create(user=self.user, preferred_budget_max=1500,
                                   preferred_duration_days=2, interests='Mountains')
        initial = self.client.get(self.url).context['form'].initial
        self.assertEqual(initial, {'budget': Decimal('1500'), 'duration': 2, 'interests': 'Mountains'})

    def test_excludes_inactive_unavailable_and_wrong_duration(self):
        for slug, changes, days, spots in [
            ('inactive', {'is_active': False}, 7, 3),
            ('past', {}, -1, 3), ('full', {}, 7, 0),
            ('long', {'duration_days': 3}, 7, 3),
            ('expensive', {'price': 3000}, 7, 3),
        ]:
            tour = self.make_tour(slug, **changes)
            TourDate.objects.create(tour=tour, date=timezone.localdate() + timedelta(days=days),
                                    available_spots=spots)
        self.make_tour('no-dates')
        self.assertEqual([item['tour'] for item in self.results(duration=2)], [self.tour])

    def test_cheapest_available_date_and_budget_boundary(self):
        TourDate.objects.create(tour=self.tour, date=timezone.localdate(), available_spots=1,
                                price_modifier=Decimal('0.80'))
        results = self.results(budget=800)
        self.assertEqual(results[0]['price'], Decimal('800'))
        self.assertEqual(self.results(budget='799.99'), [])

    def test_synonyms_stop_words_and_ranking(self):
        self.tour.description = 'Альпийский маршрут'
        self.tour.save()
        lake = self.make_tour('lake', description='Озеро', price=500)
        TourDate.objects.create(tour=lake, date=self.date.date, available_spots=1)
        results = self.results(interests='хочу горы и музей')
        self.assertEqual([item['tour'] for item in results], [self.tour, lake])
        self.assertEqual([item['match_percentage'] for item in results], [50, 0])
        results = self.results(interests='люблю и на')
        self.assertEqual([item['tour'] for item in results], [lake, self.tour])
        self.assertTrue(all(item['match_percentage'] == 100 for item in results))

    def test_results_limited_to_ten_with_stable_ties(self):
        expected = [self.tour]
        for number in range(11):
            tour = self.make_tour(f'tour-{number}')
            expected.append(tour)
            TourDate.objects.create(tour=tour, date=self.date.date, available_spots=1)
        self.assertEqual([item['tour'] for item in self.results()], expected[:10])


class ReviewTests(TravelTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url = reverse('tours:add_review', args=[self.tour.slug])
        self.detail = reverse('tours:tour_detail', args=[self.tour.slug])

    def test_only_completed_booking_allows_review(self):
        booking = self.make_booking()
        for status in ('pending', 'confirmed', 'cancelled'):
            booking.status = status
            booking.save()
            self.assertRedirects(self.client.post(self.url, {'rating': 5, 'comment': 'Great'}), self.detail)
            self.assertFalse(Review.objects.exists())

    def test_another_users_completed_booking_does_not_grant_access(self):
        self.make_booking(user=self.other, status='completed')
        self.client.post(self.url, {'rating': 5, 'comment': 'Great'})
        self.assertFalse(Review.objects.exists())

    def test_create_review_trims_comment_and_prevents_duplicates(self):
        self.make_booking(status='completed')
        for _ in range(2):
            self.assertRedirects(self.client.post(self.url, {
                'rating': 5, 'comment': '  Great  ', 'user': self.other.pk,
            }), self.detail)
        review = Review.objects.get()
        self.assertEqual((review.user, review.tour, review.rating, review.comment),
                         (self.user, self.tour, 5, 'Great'))

    def test_invalid_reviews_and_get_do_not_write(self):
        self.make_booking(status='completed')
        self.assertRedirects(self.client.get(self.url), self.detail)
        for rating, comment in [('0', 'Text'), ('6', 'Text'), ('bad', 'Text'), ('5', '  ')]:
            with self.subTest(rating=rating, comment=comment):
                self.assertRedirects(self.client.post(self.url, {'rating': rating, 'comment': comment}), self.detail)
        self.assertFalse(Review.objects.exists())

    def test_guest_redirected_to_login(self):
        self.client.logout()
        self.assertRedirects(self.client.post(self.url), reverse('login') + '?next=' + self.url)
