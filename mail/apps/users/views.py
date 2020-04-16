from django.contrib.auth import login
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic import View
import re
from .models import User
from mail.utils.response_code import RETCODE
from . import constants
from django_redis import get_redis_connection
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
        # 判断是否同意许可协议
        if allow != 'on':
            return HttpResponse('请同意许可协议')
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
        response.set_cookie('username', username, max_age=14 * 24 * 3600)
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
