from django.conf.urls import url
from . import views


urlpatterns = [
    url(r'^payment/(?P<order_id>\d+)/$',views.GetUrlView.as_view(), name='url'),
    url(r'^payment/status/$', views.PayStatusView.as_view(),name='status'),
]