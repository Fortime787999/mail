from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^areas/$', views.AreaView.as_view(), name='area'),
]