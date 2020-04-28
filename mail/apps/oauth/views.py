from django.conf import settings
from django.shortcuts import render, redirect
from QQLoginTool.QQtool import OAuthQQ
from django.views.generic import View
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseServerError
from mail.utils.response_code import RETCODE
import re
from django_redis import get_redis_connection
from .models import OAuthQQUser
from users.models import User
from django.contrib.auth import login
from mail.utils import SignatureSerializer
from carts.utils import merge_cart
from . import constants
import logging

logger = logging.getLogger('django')


# Create your views here.


class OauthView(View):

    def get(self, request):
        next = request.GET.get('next')
        oauth = OAuthQQ(client_id=settings.QQ_CLIENT_ID, client_secret=settings.QQ_CLIENT_SECRET,
                        redirect_uri=settings.QQ_REDIRECT_URI, state=next)
        login_url = oauth.get_qq_url()
        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'ok', 'login_url': login_url})


class OauthOpenidView(View):

    def get(self, request):
        oauth = OAuthQQ(client_id=settings.QQ_CLIENT_ID, client_secret=settings.QQ_CLIENT_SECRET,
                        redirect_uri=settings.QQ_REDIRECT_URI, state=next)
        code = request.GET.get('code')
        state = request.GET.get('state', '/')

        try:
            access_token = oauth.get_access_token(code)
            openid = oauth.get_open_id(access_token)
        except Exception as e:
            logger.error(e)
            return HttpResponseServerError('Oauth认证失败')
        # 判断qq是否初次授权，如果是，新建用户，否则跳转页面，并登录
        try:
            open_user = OAuthQQUser.objects.get(openid=openid)
        except Exception as e:
            # 未查询到数据，说明为初次授权
            logger.info(e)
            json_openid = SignatureSerializer.dumps({'openid': openid}, constants.OPEN_EXPIRE)
            return render(request, 'oauth_callback.html', {'token': json_openid})
        # 查询到数据，说明已经授权过，直接登录并跳转页面
        user = open_user.user
        login(request, user)
        response = redirect(state)
        response.set_cookie('username', user.username)
        merge_cart(request, response)
        return response

    def post(self, request):
        access_token = request.POST.get('access_token')
        mobile = request.POST.get('mobile')
        password = request.POST.get('pwd')
        sms_code = request.POST.get('sms_code')
        state = request.GET.get('state', '/')
        if not all([access_token, mobile, password, sms_code]):
            return HttpResponseForbidden('缺少必传参数')
        # 判断手机号是否合法
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return HttpResponseForbidden('请输入正确的手机号码')
        # 判断密码是否合格
        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return HttpResponseForbidden('请输入8-20位的密码')

        sms_conn = get_redis_connection('sms_code')
        sms_conn_code = sms_conn.get('sms_%s' % mobile)
        if sms_conn_code is None:
            return HttpResponseForbidden('验证码不存在')
        sms_conn.delete('sms_%s' % mobile)
        sms_conn.delete('flags_%s' % mobile)
        if sms_code != sms_conn_code.decode():
            return HttpResponseForbidden('验证码错误')

        # 判断openid是否有效
        openid_dict = SignatureSerializer.loads(access_token, constants.OPEN_EXPIRE)
        if openid_dict is None:
            return HttpResponseForbidden('授权信息无效，请重新授权')
        openid = openid_dict.get('openid')

        # 判断手机号是否注册，如果注册，则绑定该用户，否则注册新用户
        try:
            user = User.objects.get(mobile=mobile)
        except Exception as e:
            # 说明手机号未被注册
            logger.error(e)
            user = User.objects.create_user(username=mobile, password=password, mobile=mobile)
        else:
            # 说明手机号已被注册，检查密码是否正确
            if not user.check_password(password):
                return HttpResponseForbidden('手机号或密码错误')

        # 创建QQ用户模型与用户相绑定
        open_user = OAuthQQUser.objects.create(user=user,openid=openid)
        login(request,user)
        response = redirect(state)
        response.set_cookie('username', user.username)
        merge_cart(request, response)
        return response

