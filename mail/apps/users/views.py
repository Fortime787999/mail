from django.contrib.auth import login,authenticate,logout
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic import View
import re
from .models import User
from mail.utils.response_code import RETCODE
from . import constants
from django_redis import get_redis_connection
from mail.utils.login import LoginRequiredMixin
import logging


logger = logging.getLogger('django')


# Create your views here.


class RegisterView(View):

    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        cpassword = request.POST.get('cpwd')
        mobile = request.POST.get('phone')
        sms_code = request.POST.get('msg_code')
        allow = request.POST.get('allow')

        # 判断参数是否传入完整
        if not all([username, password, cpassword, mobile, sms_code, allow]):
            return HttpResponseForbidden('缺少必传参数')
        # 判断用户名是否为5-20个字符
        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$', username):
            return HttpResponseForbidden('用户名为5-20个字符')
        # 判断密码是否为8-20个字符
        if not re.match(r'^[a-zA-Z0-9]{8,20}$', password):
            return HttpResponseForbidden('密码为8-20个字符')
        # 判断两次密码是不是相同
        if password != cpassword:
            return HttpResponseForbidden('请输入相同的密码')
        # 判断手机号是不是符合要求
        if not re.match(r'^1[35789][0-9]{9}$', mobile):
            return HttpResponseForbidden('请输入正确的手机号')
        if User.objects.filter(mobile=mobile):
            return HttpResponseForbidden('手机号已经存在')

        sms_conn = get_redis_connection('sms_code')
        sms_conn_code = sms_conn.get('sms_%s' % mobile)
        if sms_conn_code is None:
            return HttpResponseForbidden('验证码不存在')
        sms_conn.delete('sms_%s' % mobile)
        sms_conn.delete('flags_%s' % mobile)
        if sms_code != sms_conn_code.decode():
            return HttpResponseForbidden('验证码错误')
        # 为什么要再次验证数据呢，防止数据不是从前端发送而来的，是从非正常渠道发送的
        # 保存用户数据
        try:
            user = User.objects.create_user(username=username, password=password, mobile=mobile)
        except Exception as e:
            logger.error(e)
            return render(request, 'register.html', {'register_errmsg': '注册失败'})

        # 创建用户成功，自动登录并返回首页
        login(request, user)
        response = redirect(reverse('contenes:index'))
        response.set_cookie('username', username, max_age=constants.USERNAME_COOKIE_EXPIRES)
        return response


class UsernameRepeatView(View):
    # 判断用户名是否重复
    def get(self, request, username):
        count = User.objects.filter(username=username).count()
        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'count': count})


class MobileRepeatView(View):
    # 判断手机号是否重复
    def get(self, request, mobile):
        count = User.objects.filter(mobile=mobile).count()
        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'count': count})


class LoginView(View):

    def get(self, request):
        next_url = request.GET.get('next', '/')
        if request.user.is_authenticated:
            return redirect(next_url)
        return render(request, 'login.html')

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        remembered = request.POST.get('remembered')
        next_url = request.GET.get('next', '/')

        if not all([username, password]):
            return HttpResponseForbidden('缺少传入参数')
            # 判断用户名是否为5-20个字符
        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$', username):
            return HttpResponseForbidden('用户名为5-20个字符')
        # 判断密码是否为8-20个字符
        if not re.match(r'^[a-zA-Z0-9]{8,20}$', password):
            return HttpResponseForbidden('密码为8-20个字符')
        user = authenticate(username=username, password=password)
        if user is None:
            return render(request, 'login.html', {'account_errmsg': '用户名或密码错误'})
        login(request, user)
        if remembered != 'on':
            request.session.set_expiry(0)
        else:
            request.session.set_expiry(None)
        response = redirect(next_url)
        # 向cookie中写入用户名，用于客户端展示
        response.set_cookie('username', username, max_age=constants.USERNAME_COOKIE_EXPIRES)
        return response


class LogoutView(View):

    def get(self, request):
        logout(request)
        response = redirect(reverse('users:login'))
        response.delete_cookie('username')
        return response


class UserInfoView(LoginRequiredMixin, View):

    def get(self, request):
        return render(request, 'user_center_info.html')



