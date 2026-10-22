from django.utils.translation import gettext_lazy as _
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from tours.models import Tour, TourDate
from .models import Booking, UserProfile
from .forms import BookingForm, ProfileForm
from django.utils import timezone


@login_required
def create_booking(request, tour_id, date_id):
    """Создание бронирования"""
    tour = get_object_or_404(Tour, id=tour_id, is_active=True)
    tour_date = get_object_or_404(TourDate, id=date_id, tour=tour)

    if tour_date.date < timezone.localdate() or tour_date.available_spots < 1:
        messages.error(request, _('Эта дата уже недоступна для бронирования.'))
        return redirect('tours:tour_detail', slug=tour.slug)
    form = BookingForm(request.POST if request.method == 'POST' else None, initial={
        'participants_count': 1, 'contact_name': request.user.get_full_name() or request.user.username,
        'contact_email': request.user.email,
    })
    if request.method == 'POST' and form.is_valid():
        count = form.cleaned_data['participants_count']
        if count > tour_date.available_spots:
            form.add_error('participants_count', _('Доступно только %(count)s мест.') % {'count': tour_date.available_spots})
        else:
            booking = form.save(commit=False)
            booking.user = request.user
            booking.tour = tour
            booking.tour_date = tour_date
            booking.total_price = tour_date.get_final_price() * count
            booking.save()
            messages.success(request, _('Заявка отправлена. Места закрепляются после подтверждения администратором.'))
            return redirect('bookings:booking_detail', booking_id=booking.pk)
    return render(request, 'bookings/create_booking.html', {
        'tour': tour, 'tour_date': tour_date, 'final_price': tour_date.get_final_price(), 'form': form,
    })


@login_required
def booking_list(request):
    """Личный кабинет: список бронирований пользователя"""
    bookings = Booking.objects.filter(user=request.user).select_related(
        'tour', 'tour_date'
    ).order_by('-created_at')

    context = {
        'bookings': bookings,
    }

    return render(request, 'bookings/booking_list.html', context)


@login_required
def booking_detail(request, booking_id):
    """Детальная информация о бронировании"""
    booking = get_object_or_404(
        Booking.objects.select_related('tour', 'tour_date'),
        id=booking_id,
        user=request.user
    )

    context = {
        'booking': booking,
    }

    return render(request, 'bookings/booking_detail.html', context)


@login_required
def cancel_booking(request, booking_id):
    """Отмена бронирования"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if request.method == 'POST':
        if booking.cancel():
            messages.success(request, _('Бронирование успешно отменено'))
        else:
            messages.error(request, _('Не удалось отменить бронирование'))

        return redirect('bookings:booking_list')

    context = {
        'booking': booking,
    }

    return render(request, 'bookings/cancel_booking.html', context)


@login_required
def profile_view(request):
    """Просмотр и редактирование профиля"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    form = ProfileForm(request.POST if request.method == 'POST' else None, instance=profile)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, _('Профиль обновлён.'))
        return redirect('bookings:profile')
    return render(request, 'bookings/profile.html', {'profile': profile, 'form': form})
