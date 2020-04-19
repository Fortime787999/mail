from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^register/$', views.RegisterView.as_view(), name='register'),
    url(r'^usernames/(?P<username>[a-zA-Z0-9_-]{5,20})/count/$', views.UsernameRepeatView.as_view(), name='namerepeat'),
    url(r'^mobiles/(?P<mobile>1[35789][0-9]{9})/count/$', views.MobileRepeatView.as_view(), name='mobilerepeat'),
    url(r'^login/$',views.LoginView.as_view(), name='login'),
    url(r'^logout/$', views.LogoutView.as_view(), name='logout'),
    url(r'^info/$', views.UserInfoView.as_view(), name='info'),
    url(r'^emails/$', views.EmailActiceView.as_view(), name='email'),
    url(r'^emails/verification/$', views.EmailVeriView.as_view(), name='emailveri'),
    url(r'^addresses/$', views.AddressView.as_view(), name='address'),
    url(r'^addresses/create/$', views.AddressCreateView.as_view(), name='create'),
    url(r'^addresses/(?P<address_id>\d+)/default/$', views.AddressDefaultView.as_view(), name='default'),
    url(r'^addresses/(?P<address_id>\d+)/$', views.AddressUpdateView.as_view(), name='update'),
    url(r'^addresses/(?P<address_id>\d+)/title/$', views.TitleUpdataView.as_view(), name='title'),
    url(r'^password/$', views.UserPasswordView.as_view(), name='password')
]
