from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^carts/$', views.UpdateCartView.as_view(), name='update'),
    url(r'^carts/selection/$', views.SelectedCartView.as_view(), name='selected'),
    url(r'^carts/simple/$', views.CartSimpleView.as_view(), name='simple'),
]