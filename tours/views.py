from django.utils.translation import gettext_lazy as _
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg, Count
from django.core.paginator import Paginator
from .models import Tour, TourDate, Region, TourCategory, Review
from bookings.models import Booking
from .forms import TourFilterForm, RecommendForm, CommentForm
from django.utils import timezone
from decimal import Decimal
import re
from urllib.parse import urlencode
from django.urls import reverse
from django.db import transaction
from .notifications import notify_new_comment


def tour_list(request):
    """Каталог туров с фильтрами и поиском"""
    tours = Tour.objects.filter(is_active=True).select_related('region', 'category')

    # Поиск
    search_query = request.GET.get('search', '')
    if search_query:
        tours = tours.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(region__name__icontains=search_query)
        )

    form = TourFilterForm(request.GET)
    form.is_valid()
    for field, lookup in [('region', 'region_id'), ('category', 'category_id'),
                          ('min_price', 'price__gte'), ('max_price', 'price__lte'),
                          ('duration', 'duration_days')]:
        value = form.cleaned_data.get(field)
        if value is not None:
            tours = tours.filter(**{lookup: value})
    if form.errors:
        messages.error(request, _('Проверьте значения фильтров: цена и длительность должны быть числами.'))
    difficulty = request.GET.get('difficulty')
    if difficulty in dict(Tour.DIFFICULTY_CHOICES):
        tours = tours.filter(difficulty=difficulty)
    sort_by = request.GET.get('sort', '-created_at')
    if sort_by not in ('-created_at', 'price', '-price', 'duration_days'):
        sort_by = '-created_at'
    tours = tours.order_by(sort_by, 'pk').prefetch_related('images')

    # Пагинация
    paginator = Paginator(tours, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Данные для фильтров
    regions = Region.objects.all()
    categories = TourCategory.objects.all()

    context = {
        'page_obj': page_obj,
        'regions': regions,
        'categories': categories,
        'search_query': search_query,
        'filter_query': request.GET.copy(),
    }

    context['filter_query'].pop('page', None)
    context['filter_query'] = context['filter_query'].urlencode()
    return render(request, 'tours/tour_list.html', context)


def tour_detail(request, slug):
    """Детальная страница тура"""
    tour = get_object_or_404(
        Tour.objects.select_related('region', 'category').prefetch_related('images', 'dates'),
        slug=slug,
        is_active=True
    )

    # Доступные даты
    comment_form = CommentForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?{urlencode({'next': request.path})}")
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.tour = tour
            comment.user = request.user
            comment.save()
            comment_url = request.build_absolute_uri(
                reverse('tours:tour_detail', kwargs={'slug': tour.slug}) + '#comments'
            )
            transaction.on_commit(lambda: notify_new_comment(comment, comment_url))
            messages.success(request, _('Комментарий опубликован.'))
            return redirect(f"{reverse('tours:tour_detail', kwargs={'slug': tour.slug})}#comments")

    available_dates = tour.get_available_dates()

    # Отзывы
    reviews = tour.reviews.select_related('user').all()
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']

    # Похожие туры
    similar_tours = Tour.objects.filter(
        region=tour.region,
        is_active=True
    ).exclude(id=tour.id)[:4]

    context = {
        'tour': tour,
        'available_dates': available_dates,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'similar_tours': similar_tours,
        'comments': tour.comments.filter(is_published=True).select_related('user'),
        'comment_form': comment_form,
    }

    return render(request, 'tours/tour_detail.html', context)


@login_required
def tour_recommend(request):
    """Подбор туров по бюджету и интересам (алгоритмическая часть)"""
    profile = getattr(request.user, 'profile', None)
    initial = {} if profile is None else {
        'budget': profile.preferred_budget_max, 'duration': profile.preferred_duration_days,
        'interests': profile.interests,
    }
    form = RecommendForm(request.POST if request.method == 'POST' else None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        budget = form.cleaned_data['budget']
        duration = form.cleaned_data['duration']
        interests = form.cleaned_data['interests'].lower()
        tours = Tour.objects.filter(is_active=True).select_related('category', 'region').prefetch_related('dates')
        if duration:
            tours = tours.filter(duration_days=duration)
        keywords = set(re.findall(r'[а-яёa-z]+', interests)) - {'люблю', 'хочу', 'и', 'в', 'на', 'до'}
        synonyms = {'горы': ['гор', 'альп', 'трекинг', 'пеш'], 'озера': ['озер', 'озёр', 'куль'],
                    'озёра': ['озер', 'озёр', 'куль'], 'культура': ['культур', 'музей', 'истор']}
        scored_tours = []
        for tour in tours:
            prices = [date.get_final_price() for date in tour.dates.all()
                      if date.date >= timezone.localdate() and date.available_spots > 0
                      and date.get_final_price() <= budget]
            if not prices:
                continue
            text = f'{tour.name} {tour.description} {tour.route} {tour.category or ""} {tour.region}'.lower()
            matches = sum(any(term in text for term in synonyms.get(word, [word])) for word in keywords)
            score = matches / len(keywords) if keywords else 1
            scored_tours.append({'tour': tour, 'score': matches, 'match_percentage': round(score * 100),
                                 'price': min(prices)})
        scored_tours.sort(key=lambda item: (-item['match_percentage'], item['price'], item['tour'].pk))
        return render(request, 'tours/recommend_results.html', {
            'scored_tours': scored_tours[:10], 'budget': budget, 'duration': duration, 'interests': interests,
        })
    return render(request, 'tours/recommend.html', {'form': form})


@login_required
def add_review(request, slug):
    """Добавление отзыва о туре"""
    tour = get_object_or_404(Tour, slug=slug)

    # Проверяем, был ли пользователь на этом туре
    has_completed_booking = Booking.objects.filter(
        user=request.user,
        tour=tour,
        status='completed'
    ).exists()

    if not has_completed_booking:
        messages.error(request, _('Вы можете оставить отзыв только после завершения тура'))
        return redirect('tours:tour_detail', slug=slug)

    # Проверяем, не оставлял ли пользователь уже отзыв
    if Review.objects.filter(user=request.user, tour=tour).exists():
        messages.error(request, _('Вы уже оставили отзыв на этот тур'))
        return redirect('tours:tour_detail', slug=slug)

    if request.method == 'POST':
        rating = request.POST.get('rating', '')
        comment = request.POST.get('comment', '').strip()
        if rating not in ('1', '2', '3', '4', '5') or not comment:
            messages.error(request, _('Укажите оценку от 1 до 5 и текст отзыва.'))
            return redirect('tours:tour_detail', slug=slug)

        Review.objects.create(
            tour=tour,
            user=request.user,
            rating=rating,
            comment=comment
        )

        messages.success(request, _('Спасибо за ваш отзыв!'))
        return redirect('tours:tour_detail', slug=slug)

    return redirect('tours:tour_detail', slug=slug)
