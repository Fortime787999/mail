from django.conf.urls import url
from . import views


urlpatterns = [
    url(r'^orders/settlement/$', views.OrderView.as_view(), name='settlement'),
    url(r'^orders/commit/$', views.OrderCommitView.as_view(), name='commit'),
    url(r'^orders/success/$', views.OrderSuccessView.as_view(), name='success'),
    url(r'^orders/info/(?P<page_num>\d+)/$', views.OrderInfoView.as_view(), name='info')
]