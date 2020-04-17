from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^qq/login/$',views.OauthView.as_view(), name='qqlogin'),
    url(r'^oauth_callback/$',views.OauthOpenidView.as_view(), name='callback')
]