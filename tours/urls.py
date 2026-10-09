from django.urls import path
from . import views

app_name = 'tours'

urlpatterns = [
    path('', views.tour_list, name='tour_list'),
    path('recommend/', views.tour_recommend, name='tour_recommend'),
    path('<slug:slug>/', views.tour_detail, name='tour_detail'),
    path('<slug:slug>/review/', views.add_review, name='add_review'),
]
