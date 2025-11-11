from django.urls import path
from . import views

urlpatterns = [
	path('geocode', views.geocode_view, name='geocode'),
	path('route', views.route_view, name='route'),
]


