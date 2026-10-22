from django.utils.translation import gettext_lazy as _
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal


class Region(models.Model):
    """Регион для туров (Иссык-Куль, Сон-Куль, Ала-Арча и т.д.)"""
    name = models.CharField(max_length=100, verbose_name=_('Название региона'))
    description = models.TextField(verbose_name=_('Описание региона'), blank=True)

    class Meta:
        verbose_name = "Регион"
        verbose_name_plural = "Регионы"

    def __str__(self):
        return self.name


class TourCategory(models.Model):
    """Категория тура (горы, озера, культурные и т.д.)"""
    name = models.CharField(max_length=100, verbose_name=_('Название категории'))

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name


class Tour(models.Model):
    """Основная модель тура"""
    DIFFICULTY_CHOICES = [
        ('easy', _('Легкий')),
        ('medium', _('Средний')),
        ('hard', _('Сложный')),
    ]

    name = models.CharField(max_length=200, verbose_name=_('Название тура'))
    slug = models.SlugField(max_length=200, unique=True, verbose_name="URL")
    description = models.TextField(verbose_name=_('Описание'))
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='tours', verbose_name=_('Регион'))
    category = models.ForeignKey(TourCategory, on_delete=models.SET_NULL, null=True, related_name='tours', verbose_name=_('Категория'))

    duration_days = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name=_('Длительность (дней)'))
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium', verbose_name=_('Сложность'))

    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], verbose_name=_('Цена (сом)'))

    route = models.TextField(verbose_name=_('Маршрут'), help_text=_('Описание маршрута поездки'))
    included = models.TextField(verbose_name=_('Что включено'), blank=True)
    not_included = models.TextField(verbose_name=_('Что не включено'), blank=True)

    max_participants = models.PositiveIntegerField(default=15, verbose_name=_('Максимум участников'))

    is_active = models.BooleanField(default=True, verbose_name=_('Активен'))
    is_featured = models.BooleanField(default=False, verbose_name=_('Рекомендуемый тур'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Дата создания'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Дата обновления'))

    class Meta:
        verbose_name = "Тур"
        verbose_name_plural = "Туры"
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_available_dates(self):
        """Возвращает доступные даты для бронирования"""
        from django.utils import timezone
        return self.dates.filter(date__gte=timezone.localdate(), available_spots__gt=0)


class TourImage(models.Model):
    """Фотографии тура"""
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='images', verbose_name=_('Тур'))
    image = models.ImageField(upload_to='tours/%Y/%m/%d/', verbose_name=_('Фотография'))
    caption = models.CharField(max_length=200, blank=True, verbose_name=_('Подпись'))
    is_main = models.BooleanField(default=False, verbose_name=_('Главное фото'))
    order = models.PositiveIntegerField(default=0, verbose_name=_('Порядок'))

    class Meta:
        verbose_name = "Фотография"
        verbose_name_plural = "Фотографии"
        ordering = ['order', '-is_main']

    def __str__(self):
        return f"Фото для {self.tour.name}"


class TourDate(models.Model):
    """Конкретные даты проведения тура"""
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='dates', verbose_name=_('Тур'))
    date = models.DateField(verbose_name=_('Дата начала'))
    end_date = models.DateField(verbose_name=_('Дата окончания'), blank=True, null=True)
    available_spots = models.PositiveIntegerField(verbose_name=_('Свободных мест'))
    price_modifier = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Модификатор цены'),
        help_text=_('1.00 = базовая цена, 1.20 = +20%, 0.80 = -20%')
    )

    class Meta:
        verbose_name = "Дата тура"
        verbose_name_plural = "Даты туров"
        ordering = ['date']
        unique_together = ['tour', 'date']

    def __str__(self):
        return f"{self.tour.name} - {self.date}"

    def get_final_price(self):
        """Возвращает финальную цену с учетом модификатора"""
        return (self.tour.price * self.price_modifier).quantize(Decimal('0.01'))

    def clean(self):
        super().clean()
        if self.end_date and self.date and self.end_date < self.date:
            raise ValidationError({'end_date': 'Дата окончания должна быть не раньше начала.'})

    def is_available(self):
        """Проверяет, есть ли свободные места"""
        return self.available_spots > 0


class Comment(models.Model):
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='comments', verbose_name=_('Тур'))
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tour_comments', verbose_name=_('Автор'))
    subject = models.CharField(max_length=100, verbose_name=_('Тема комментария'))
    text = models.TextField(max_length=2000, verbose_name=_('Текст сообщения'))
    is_published = models.BooleanField(default=True, verbose_name=_('Опубликован'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Дата создания'))

    class Meta:
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return self.subject


class Review(models.Model):
    """Отзывы о турах"""
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='reviews', verbose_name=_('Тур'))
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews', verbose_name=_('Пользователь'))
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_('Оценка')
    )
    comment = models.TextField(verbose_name=_('Комментарий'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Дата создания'))

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        ordering = ['-created_at']
        unique_together = ['tour', 'user']

    def __str__(self):
        return f"Отзыв от {self.user.username} на {self.tour.name}"
