from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from .models import Booking, UserProfile


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'tour', 'tour_date_info', 'participants_count', 'total_price', 'status_badge', 'created_at']
    list_filter = ['status', 'created_at', 'tour__region']
    search_fields = ['user__username', 'tour__name', 'contact_name', 'contact_phone']
    readonly_fields = ['created_at', 'updated_at', 'confirmed_at', 'total_price', 'status', 'user', 'tour', 'tour_date', 'participants_count']
    date_hierarchy = 'created_at'

    actions = ['confirm_bookings', 'cancel_bookings', 'complete_bookings']

    fieldsets = (
        ('Информация о бронировании', {
            'fields': ('user', 'tour', 'tour_date', 'participants_count', 'total_price', 'status')
        }),
        ('Контактная информация', {
            'fields': ('contact_name', 'contact_phone', 'contact_email', 'special_requests')
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at', 'confirmed_at')
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def tour_date_info(self, obj):
        return obj.tour_date.date.strftime('%d.%m.%Y')
    tour_date_info.short_description = 'Дата тура'

    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'confirmed': 'green',
            'cancelled': 'red',
            'completed': 'blue',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Статус'

    def confirm_bookings(self, request, queryset):
        """Массовое подтверждение бронирований"""
        pending_count = queryset.filter(status='pending').count()
        confirmed_count = 0
        for booking in queryset.filter(status='pending'):
            if booking.confirm():
                confirmed_count += 1

        self.message_user(
            request,
            f'Подтверждено: {confirmed_count}. Не подтверждено: {pending_count - confirmed_count}; проверьте даты и свободные места.',
            messages.WARNING if confirmed_count < pending_count else messages.SUCCESS
        )
    confirm_bookings.short_description = 'Подтвердить выбранные бронирования'

    @admin.action(description='Отметить завершённые поездки')
    def complete_bookings(self, request, queryset):
        from django.utils import timezone
        from django.db.models import Q
        today = timezone.localdate()
        count = queryset.filter(status='confirmed').filter(Q(tour_date__end_date__lt=today) | Q(tour_date__end_date__isnull=True, tour_date__date__lt=today)).update(status='completed', updated_at=timezone.now())
        self.message_user(request, f'Завершено заявок: {count}')

    def cancel_bookings(self, request, queryset):
        """Массовая отмена бронирований"""
        cancelled_count = 0
        for booking in queryset:
            if booking.cancel():
                cancelled_count += 1

        self.message_user(
            request,
            f'Успешно отменено {cancelled_count} бронирований',
            messages.SUCCESS
        )
    cancel_bookings.short_description = 'Отменить выбранные бронирования'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'bookings_count', 'created_at']
    list_filter = ['created_at', 'user__is_active']
    search_fields = ['user__username', 'user__email', 'phone']
    readonly_fields = ['created_at', 'bookings_count']

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'phone', 'date_of_birth')
        }),
        ('Предпочтения', {
            'fields': ('preferred_budget_min', 'preferred_budget_max', 'preferred_duration_days', 'interests')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'bookings_count')
        }),
    )

    def bookings_count(self, obj):
        return obj.user.bookings.count() if obj.user_id else 0
    bookings_count.short_description = 'Кол-во бронирований'
