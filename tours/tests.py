from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import CommentForm
from .models import Comment, Region, Tour


class CommentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='reader')
        self.tour = Tour.objects.create(
            name='Тур', slug='test-tour', description='Описание',
            region=Region.objects.create(name='Регион'),
            duration_days=1, price=1000, route='Маршрут',
        )
        self.url = reverse('tours:tour_detail', args=[self.tour.slug])

    def test_required_and_length_validation(self):
        for subject, text in [('', 'Текст'), ('Тема', ''), ('  ', '\n '),
                              ('x' * 101, 'Текст'), ('Тема', 'x' * 2001)]:
            with self.subTest(subject=subject, text=text):
                self.assertFalse(CommentForm(data={'subject': subject, 'text': text}).is_valid())
        self.assertTrue(CommentForm(data={'subject': 'x' * 100, 'text': 'x' * 2000}).is_valid())

    def test_publish_and_preserve_invalid_input(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {'subject': 'Вопрос', 'text': '  '})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['comment_form'].errors)
        self.assertContains(response, 'Вопрос')
        self.assertFalse(Comment.objects.exists())
        response = self.client.post(self.url, {
            'subject': '  Тема  ', 'text': 'Сообщение', 'user': 999, 'is_published': False,
        })
        self.assertRedirects(response, self.url + '#comments')
        comment = Comment.objects.get()
        self.assertEqual(comment.subject, 'Тема')
        self.assertEqual(comment.user, self.user)
        self.assertEqual(comment.tour, self.tour)
        self.assertTrue(comment.is_published)

    def test_guest_cannot_publish(self):
        response = self.client.post(self.url, {'subject': 'Тема', 'text': 'Текст'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Comment.objects.exists())

    def test_admin_unpublish_and_republish(self):
        comment = Comment.objects.create(tour=self.tour, user=self.user,
                                         subject='Тема', text='<script>alert(1)</script>')
        model_admin = admin.site._registry[Comment]
        queryset = Comment.objects.filter(pk=comment.pk)
        self.assertContains(self.client.get(self.url), '&lt;script&gt;')
        model_admin.unpublish(None, queryset)
        self.assertNotContains(self.client.get(self.url), '&lt;script&gt;')
        self.assertTrue(queryset.exists())
        model_admin.publish(None, queryset)
        self.assertContains(self.client.get(self.url), '&lt;script&gt;')

    def test_inactive_tour_cannot_receive_comments(self):
        self.client.force_login(self.user)
        self.tour.is_active = False
        self.tour.save()
        self.assertEqual(self.client.post(self.url, {'subject': 'Тема', 'text': 'Текст'}).status_code, 404)
        self.assertFalse(Comment.objects.exists())
