from django.contrib.auth import login
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic import View
import re
from .models import User
from mail.utils.response_code import RETCODE
from . import constants


# Create your views here.


class RegisterView(View):

    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        cpassword = request.POST.get('password2')
        mobile = request.POST.get('mobile')
        allow = request.POST.get('allow')

        # 判断参数是否传入完整
        if not all([username, password, cpassword, mobile, allow]):
            return HttpResponse('缺少必传参数')
        # 判断用户名是否为5-20个字符
        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$', username):
            return HttpResponse('用户名为5-20个字符')
        # 判断密码是否为8-20个字符
        if not re.match(r'^[a-zA-Z0-9]$', password):
            return HttpResponse('密码为8-20个字符')
        # 判断两次密码是不是相同
        if password != cpassword:
            return HttpResponse('请输入相同的密码')
        # 判断手机号是不是符合要求
        if not re.match(r'^1[35789][0-9]{9}$', mobile):
            return HttpResponse('请输入正确的手机号')
        # 判断是否同意许可协议
        if allow != 'on':
            return HttpResponse('请同意许可协议')

        # 为什么要再次验证数据呢，防止数据不是从前端发送而来的，是从非正常渠道发送的
        # 保存用户数据
        try:
            user = User.objects.create_user(username=username, password=password, mobile=mobile)
        except Exception as e:
            return render(request, 'register.html', {'register_errmsg': '注册失败，请重试'})

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
