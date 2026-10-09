from django import forms


class TourFilterForm(forms.Form):
    region = forms.IntegerField(required=False, min_value=1)
    category = forms.IntegerField(required=False, min_value=1)
    min_price = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=2)
    max_price = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=2)
    duration = forms.IntegerField(required=False, min_value=1)


class RecommendForm(forms.Form):
    budget = forms.DecimalField(label='Бюджет на человека, сом', min_value=1, max_digits=10, decimal_places=2)
    duration = forms.IntegerField(label='Длительность, дней', required=False, min_value=1)
    interests = forms.CharField(label='Интересы', required=False, max_length=300)
