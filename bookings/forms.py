from django import forms
from .models import Booking, UserProfile


class BookingForm(forms.ModelForm):
    participants_count = forms.IntegerField(min_value=1, label='Количество человек')

    class Meta:
        model = Booking
        fields = ['participants_count', 'contact_name', 'contact_phone', 'contact_email', 'special_requests']


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone', 'preferred_budget_min', 'preferred_budget_max', 'preferred_duration_days', 'interests']

    def clean(self):
        data = super().clean()
        low, high = data.get('preferred_budget_min'), data.get('preferred_budget_max')
        for field in ('preferred_budget_min', 'preferred_budget_max'):
            if data.get(field) is not None and data[field] < 0:
                self.add_error(field, 'Бюджет не может быть отрицательным.')
        if low is not None and high is not None and low > high:
            self.add_error('preferred_budget_max', 'Максимум должен быть не меньше минимума.')
        if data.get('preferred_duration_days') == 0:
            self.add_error('preferred_duration_days', 'Укажите хотя бы один день.')
        return data
