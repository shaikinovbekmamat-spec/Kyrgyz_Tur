from django.contrib import admin
from django.utils.html import format_html
from .models import Region, TourCategory, Tour, TourImage, TourDate, Review, Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['subject', 'tour', 'user', 'is_published', 'created_at']
    list_filter = ['is_published', 'created_at', 'tour']
    search_fields = ['subject', 'text', 'user__username', 'tour__name']
    readonly_fields = ['created_at']
    list_editable = ['is_published']
    actions = ['publish', 'unpublish']

    @admin.action(description='Опубликовать выбранные комментарии')
    def publish(self, request, queryset):
        queryset.update(is_published=True)

    @admin.action(description='Снять выбранные комментарии с публикации')
    def unpublish(self, request, queryset):
        queryset.update(is_published=False)


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ['name', 'tours_count']
    search_fields = ['name', 'description']
    readonly_fields = ['tours_count']

    def tours_count(self, obj):
        return obj.tours.count() if obj.pk else 0
    tours_count.short_description = 'Количество туров'


@admin.register(TourCategory)
class TourCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'tours_count']
    search_fields = ['name']
    readonly_fields = ['tours_count']

    def tours_count(self, obj):
        return obj.tours.count() if obj.pk else 0
    tours_count.short_description = 'Количество туров'


class TourImageInline(admin.TabularInline):
    model = TourImage
    extra = 1
    fields = ['image', 'caption', 'is_main', 'order']


class TourDateInline(admin.TabularInline):
    model = TourDate
    extra = 1
    fields = ['date', 'end_date', 'available_spots', 'price_modifier']


@admin.register(Tour)
class TourAdmin(admin.ModelAdmin):
    list_display = ['name', 'region', 'category', 'duration_days', 'price', 'difficulty', 'is_active', 'created_at']
    list_filter = ['is_active', 'region', 'category', 'difficulty', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    inlines = [TourImageInline, TourDateInline]

    # is_featured не используется на сайте и исключён из формы через fieldsets.
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'slug', 'description', 'region', 'category')
        }),
        ('Детали тура', {
            'fields': ('duration_days', 'difficulty', 'price', 'max_participants')
        }),
        ('Маршрут и условия', {
            'fields': ('route', 'included', 'not_included')
        }),
        ('Статус', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )


@admin.register(TourImage)
class TourImageAdmin(admin.ModelAdmin):
    list_display = ['tour', 'image_preview', 'caption', 'is_main', 'order']
    list_filter = ['is_main', 'tour']
    search_fields = ['tour__name', 'caption']
    list_editable = ['is_main', 'order']
    readonly_fields = ['image_preview']

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 100px; height: auto;" />', obj.image.url)
        return '-'
    image_preview.short_description = 'Превью'


@admin.register(TourDate)
class TourDateAdmin(admin.ModelAdmin):
    list_display = ['tour', 'date', 'end_date', 'available_spots', 'price_modifier', 'final_price', 'status_badge']
    list_filter = ['date', 'tour__region']
    search_fields = ['tour__name']
    date_hierarchy = 'date'
    readonly_fields = ['final_price', 'status_badge']

    def final_price(self, obj):
        if not obj.pk:
            return '-'
        return f"{obj.get_final_price()} сом"
    final_price.short_description = 'Финальная цена'

    def status_badge(self, obj):
        if not obj.pk:
            return '-'
        if obj.is_available():
            return format_html('<span style="color: green;">{}</span>', '✓ Доступно')
        return format_html('<span style="color: red;">{}</span>', '✗ Нет мест')
    status_badge.short_description = 'Статус'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['tour', 'user', 'rating', 'created_at', 'comment_preview']
    list_filter = ['rating', 'created_at', 'tour']
    search_fields = ['tour__name', 'user__username', 'comment']
    readonly_fields = ['created_at']

    def comment_preview(self, obj):
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
    comment_preview.short_description = 'Комментарий'
