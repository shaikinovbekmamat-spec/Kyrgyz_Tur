from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from tours.models import Region, TourCategory, Tour, TourDate


class Command(BaseCommand):
    help = 'Добавляет демонстрационные туры без изменения существующих данных.'

    def handle(self, *args, **options):
        examples = [
            ('issyk-kul', 'Выходные на Иссык-Куле', 'Иссык-Куль', 'Озёра', 2, 4500, 'Озеро и прогулки по берегу.'),
            ('son-kul', 'Юрты и горы Сон-Куля', 'Сон-Куль', 'Горы', 2, 5000, 'Горы, озеро и ночёвка в юрте.'),
            ('ala-archa', 'Прогулка в Ала-Арче', 'Ала-Арча', 'Горы', 1, 1800, 'Горный трекинг по ущелью.'),
        ]
        for slug, name, region_name, category_name, days, price, description in examples:
            region, _ = Region.objects.get_or_create(name=region_name)
            category, _ = TourCategory.objects.get_or_create(name=category_name)
            tour, _ = Tour.objects.get_or_create(slug=slug, defaults={
                'name': name, 'region': region, 'category': category, 'duration_days': days,
                'price': price, 'description': description, 'route': f'Бишкек → {region_name} → Бишкек',
                'included': 'Транспорт и сопровождение гида',
            })
            for offset in (7, 14, 21):
                date = timezone.localdate() + timedelta(days=offset)
                TourDate.objects.get_or_create(tour=tour, date=date, defaults={
                    'end_date': date + timedelta(days=tour.duration_days - 1), 'available_spots': 15,
                })
        self.stdout.write(self.style.SUCCESS('Демонстрационные туры добавлены. Фотографии загрузите в админке.'))
