from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal


class Region(models.Model):
    """Регион для туров (Иссык-Куль, Сон-Куль, Ала-Арча и т.д.)"""
    name = models.CharField(max_length=100, verbose_name="Название региона")
    description = models.TextField(verbose_name="Описание региона", blank=True)

    class Meta:
        verbose_name = "Регион"
        verbose_name_plural = "Регионы"

    def __str__(self):
        return self.name


class TourCategory(models.Model):
    """Категория тура (горы, озера, культурные и т.д.)"""
    name = models.CharField(max_length=100, verbose_name="Название категории")

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name


class Tour(models.Model):
    """Основная модель тура"""
    DIFFICULTY_CHOICES = [
        ('easy', 'Легкий'),
        ('medium', 'Средний'),
        ('hard', 'Сложный'),
    ]

    name = models.CharField(max_length=200, verbose_name="Название тура")
    slug = models.SlugField(max_length=200, unique=True, verbose_name="URL")
    description = models.TextField(verbose_name="Описание")
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='tours', verbose_name="Регион")
    category = models.ForeignKey(TourCategory, on_delete=models.SET_NULL, null=True, related_name='tours', verbose_name="Категория")

    duration_days = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="Длительность (дней)")
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium', verbose_name="Сложность")

    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Цена (сом)")

    route = models.TextField(verbose_name="Маршрут", help_text="Описание маршрута поездки")
    included = models.TextField(verbose_name="Что включено", blank=True)
    not_included = models.TextField(verbose_name="Что не включено", blank=True)

    max_participants = models.PositiveIntegerField(default=15, verbose_name="Максимум участников")

    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

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
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='images', verbose_name="Тур")
    image = models.ImageField(upload_to='tours/%Y/%m/%d/', verbose_name="Фотография")
    caption = models.CharField(max_length=200, blank=True, verbose_name="Подпись")
    is_main = models.BooleanField(default=False, verbose_name="Главное фото")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок")

    class Meta:
        verbose_name = "Фотография"
        verbose_name_plural = "Фотографии"
        ordering = ['order', '-is_main']

    def __str__(self):
        return f"Фото для {self.tour.name}"


class TourDate(models.Model):
    """Конкретные даты проведения тура"""
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='dates', verbose_name="Тур")
    date = models.DateField(verbose_name="Дата начала")
    end_date = models.DateField(verbose_name="Дата окончания", blank=True, null=True)
    available_spots = models.PositiveIntegerField(verbose_name="Свободных мест")
    price_modifier = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Модификатор цены",
        help_text="1.00 = базовая цена, 1.20 = +20%, 0.80 = -20%"
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


class Review(models.Model):
    """Отзывы о турах"""
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='reviews', verbose_name="Тур")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews', verbose_name="Пользователь")
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Оценка"
    )
    comment = models.TextField(verbose_name="Комментарий")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        ordering = ['-created_at']
        unique_together = ['tour', 'user']

    def __str__(self):
        return f"Отзыв от {self.user.username} на {self.tour.name}"
