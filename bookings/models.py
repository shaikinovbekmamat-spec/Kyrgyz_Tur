from django.db import models
from django.contrib.auth.models import User
from tours.models import Tour, TourDate
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError


class Booking(models.Model):
    """Модель бронирования тура"""
    STATUS_CHOICES = [
        ('pending', 'Ожидает подтверждения'),
        ('confirmed', 'Подтверждено'),
        ('cancelled', 'Отменено'),
        ('completed', 'Завершено'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings', verbose_name="Пользователь")
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='bookings', verbose_name="Тур")
    tour_date = models.ForeignKey(TourDate, on_delete=models.CASCADE, related_name='bookings', verbose_name="Дата тура")

    participants_count = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="Количество участников")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Общая стоимость")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус")

    # Контактная информация
    contact_name = models.CharField(max_length=200, verbose_name="Контактное имя")
    contact_phone = models.CharField(max_length=20, verbose_name="Телефон")
    contact_email = models.EmailField(verbose_name="Email")

    special_requests = models.TextField(blank=True, verbose_name="Особые пожелания")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата подтверждения")

    class Meta:
        verbose_name = "Бронирование"
        verbose_name_plural = "Бронирования"
        ordering = ['-created_at']

    def __str__(self):
        return f"Бронирование #{self.id} - {self.user.username} - {self.tour.name}"

    def clean(self):
        super().clean()
        if self.tour_date_id and self.tour_id and self.tour_date.tour_id != self.tour_id:
            raise ValidationError({'tour_date': 'Дата должна относиться к выбранному туру.'})

    def confirm(self):
        from django.db import transaction
        from django.db.models import F
        from django.utils import timezone
        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(pk=self.pk)
            if booking.status != 'pending' or booking.participants_count < 1:
                return False
            changed = TourDate.objects.filter(
                pk=booking.tour_date_id, tour_id=booking.tour_id,
                tour__is_active=True, date__gte=timezone.localdate(),
                available_spots__gte=booking.participants_count,
            ).update(available_spots=F('available_spots') - booking.participants_count)
            if not changed:
                return False
            updated = Booking.objects.filter(pk=booking.pk, status='pending').update(
                status='confirmed', confirmed_at=timezone.now(), updated_at=timezone.now())
            if not updated:
                transaction.set_rollback(True)
                return False
        self.refresh_from_db()
        return True

    def cancel(self):
        from django.db import transaction
        from django.db.models import F
        from django.utils import timezone
        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(pk=self.pk)
            if booking.status not in ('pending', 'confirmed'):
                return False
            updated = Booking.objects.filter(pk=booking.pk, status=booking.status).update(
                status='cancelled', updated_at=timezone.now())
            if not updated:
                return False
            if booking.status == 'confirmed':
                TourDate.objects.filter(pk=booking.tour_date_id).update(
                    available_spots=F('available_spots') + booking.participants_count)
        self.refresh_from_db()
        return True


class UserProfile(models.Model):
    """Расширенный профиль пользователя"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name="Пользователь")

    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Дата рождения")

    # Предпочтения для алгоритма подбора
    preferred_budget_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Минимальный бюджет")
    preferred_budget_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Максимальный бюджет")
    preferred_duration_days = models.PositiveIntegerField(null=True, blank=True, verbose_name="Предпочитаемая длительность")
    interests = models.TextField(blank=True, verbose_name="Интересы", help_text="Горы, озера, культура и т.д.")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self):
        return f"Профиль {self.user.username}"
