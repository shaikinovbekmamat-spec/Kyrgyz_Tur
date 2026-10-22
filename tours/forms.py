from django.utils.translation import gettext_lazy as _
from django import forms
from .models import Comment


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['subject', 'text']
        widgets = {
            'subject': forms.TextInput(attrs={'placeholder': _('Например: вопрос о маршруте')}),
            'text': forms.Textarea(attrs={'rows': 5, 'placeholder': _('Напишите ваш комментарий')}),
        }
        help_texts = {
            'subject': _('Обязательное поле. Не более 100 символов.'),
            'text': _('Обязательное поле. Не более 2000 символов.'),
        }
        error_messages = {
            'subject': {'required': _('Введите тему комментария.')},
            'text': {'required': _('Введите текст сообщения.')},
        }


class TourFilterForm(forms.Form):
    region = forms.IntegerField(required=False, min_value=1)
    category = forms.IntegerField(required=False, min_value=1)
    min_price = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=2)
    max_price = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=2)
    duration = forms.IntegerField(required=False, min_value=1)


class RecommendForm(forms.Form):
    budget = forms.DecimalField(label=_('Бюджет на человека, сом'), min_value=1, max_digits=10, decimal_places=2)
    duration = forms.IntegerField(label=_('Длительность, дней'), required=False, min_value=1)
    interests = forms.CharField(label=_('Интересы'), required=False, max_length=300)
