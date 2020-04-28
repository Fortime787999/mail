from django.shortcuts import render
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseServerError
from django.views.generic import View
from goods.models import SKU
from django_redis import get_redis_connection
from mail.utils.response_code import RETCODE
from . import constants
import json
import base64
import pickle
import logging

logger = logging.getLogger('django')


# Create your views here.


class UpdateCartView(View):

    def post(self, request):
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')
        count = json_dict.get('count')
        selected = json_dict.get('selected', True)
        if not all([sku_id, count]):
            return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '参数不完整'})
        try:
            sku = SKU.objects.get(id=sku_id)
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '商品编号无效'})
        try:
            count = int(count)
            if count > 5:
                return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '购买数量不能超过5个'})
            elif count < 1:
                return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '购买数量不能少于1个'})
            elif count > sku.stock:
                return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '商品库存不足'})
        except Exception as e:
            return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '请输入正确的数量'})
        if not isinstance(selected, bool):
            return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '参数无效'})

        response = JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})

        user = request.user
        if user.is_authenticated:
            redis_conn = get_redis_connection('carts')
            pipe_line = redis_conn.pipeline()
            pipe_line.hincrby('cart_%s' % user.id, sku_id, count)
            if selected:
                pipe_line.sadd('selected_%s' % user.id, sku_id)
            pipe_line.execute()
        else:
            cart_str = request.COOKIES.get('carts')
            # 存在cookie购物车
            if cart_str:
                cart_cookie_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                cart_cookie_dict = {}
            # 判断商品是否在cookie购物车中
            if sku_id in cart_cookie_dict:
                origin_count = cart_cookie_dict[sku_id]['count']
                count += origin_count
            cart_cookie_dict[sku_id] = {
                'count': count,
                'selected': selected
            }
            cart_cookie_str = base64.b64encode(pickle.dumps(cart_cookie_dict)).decode()
            response.set_cookie('carts', cart_cookie_str, max_age=constants.CARTS_COOKIE_EXPIRES)
        return response

    def get(self, request):
        user = request.user
        if user.is_authenticated:
            redis_conn = get_redis_connection('carts')
            cart_redis = redis_conn.hgetall('cart_%s' % user.id)
            cart_selected = redis_conn.smembers('selected_%s' % user.id)

            cart_dict = {}
            # 构造数据与cookie中数据一致，减少重复代码编写
            for sku_id, count in cart_redis.items():
                cart_dict[int(sku_id)] = {
                    'count': int(count),
                    'selected': int(sku_id) in cart_selected
                }
        else:
            cart_str = request.COOKIES.get('carts')
            if cart_str:
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                cart_dict = {}

        sku_ids = cart_dict.keys()
        try:
            skus = SKU.objects.filter(id__in=sku_ids)
            cart_skus = []
            for sku in skus:
                cart_skus.append({
                    'id': sku.id,
                    'name': sku.name,
                    'count': cart_dict.get(sku.id).get('count'),
                    'price': str(sku.price),
                    'selected': str(cart_dict.get(sku.id).get('selected')),
                    'amount': str(sku.price * cart_dict.get(sku.id).get('count')),
                    'default_image_url': sku.default_image.url,
                })
        except Exception as e:
            logger.error(e)
            return HttpResponseServerError('出现错误，请重试')

        context = {
            'cart_skus': cart_skus,
        }

        return render(request, 'cart.html', context=context)

    def put(self, request):
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')
        count = json_dict.get('count')
        selected = json_dict.get('selected', True)
        if not all([sku_id, count]):
            return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '参数不完整'})
        try:
            sku = SKU.objects.get(id=sku_id)
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '商品编号无效'})
        try:
            count = int(count)
            if count > 5:
                return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '购买数量不能超过5个'})
            elif count < 1:
                return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '购买数量不能少于1个'})
            elif count > sku.stock:
                return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '商品库存不足'})
        except Exception as e:
            return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '请输入正确的数量'})
        if not isinstance(selected, bool):
            return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '参数无效'})

        cart_sku = {
            'id': sku_id,
            'count': count,
            'selected': str(selected),
            'name': sku.name,
            'default_image_url': sku.default_image.url,
            'price': str(sku.price),
            'amount': str(sku.price * count),
        }
        response = JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'cart_sku': cart_sku})

        user = request.user
        if user.is_authenticated:
            redis_conn = get_redis_connection('carts')
            pipe_line = redis_conn.pipeline()
            pipe_line.hset('cart_%s' % user.id, sku_id, count)
            if selected:
                pipe_line.sadd('selected_%s' % user.id, sku_id)
            else:
                pipe_line.srem('selected_%s' % user.id, sku_id)
            pipe_line.execute()

        else:
            cart_str = request.COOKIES.get('carts')
            if cart_str:
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                cart_dict = {}
            cart_dict[sku_id] = {
                'count': count,
                'selected': selected
            }
            cart_cookie_str = base64.b64encode(pickle.dumps(cart_dict)).decode()
            response.set_cookie('carts', cart_cookie_str, max_age=constants.CARTS_COOKIE_EXPIRES)

        return response

    def delete(self, request):
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')
        if not sku_id:
            return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '缺少必需参数'})
        try:
            sku = SKU.objects.get(id=sku_id)
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '商品不存在'})
        response = JsonResponse({
            'code': RETCODE.OK,
            'errmsg': 'OK'
        })

        user = request.user
        if user.is_authenticated:
            redis_conn = get_redis_connection('carts')
            pipe_line = redis_conn.pipeline()
            pipe_line.hdel('cart_%s' % user.id, sku_id)
            pipe_line.srem('selected_%s' % user.id, sku_id)
            pipe_line.execute()
        else:
            cart_str = request.COOKIES.get('carts')
            if cart_str:
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                cart_dict = {}
            if sku_id in cart_dict:
                del cart_dict[sku_id]
            cart_cookie_str = base64.b64encode(pickle.dumps(cart_dict)).decode()
            response.set_cookie('carts_%s' % user.id, cart_cookie_str, max_age=constants.CARTS_COOKIE_EXPIRES)

        return response


class SelectedCartView(View):

    def put(self, request):
        json_dict = json.loads(request.body.decode())
        selected = json_dict.get('selected')
        if not isinstance(selected, bool):
            return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '参数selected有误'})

        response = JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})
        user = request.user
        if user.is_authenticated:
            redis_conn = get_redis_connection('carts')
            sku_ids = redis_conn.hkeys('cart_%s' % user.id)
            if selected:
                redis_conn.sadd('selected_%s' % user.id, *sku_ids)
            else:
                redis_conn.srem('selected_%s' % user.id, *sku_ids)
        else:
            cart_str = request.COOKIES.get('carts')
            if cart_str:
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                cart_dict = {}
            for cart_sku_id in cart_dict:
                cart_dict[cart_sku_id]['selected'] = selected
            cart_cookie_str = base64.b64encode(pickle.dumps(cart_dict)).decode()
            response.set_cookie('carts_%s' % user.id, cart_cookie_str, max_age=constants.CARTS_COOKIE_EXPIRES)

        return response


class CartSimpleView(View):

    def get(self, request):
        # 从购物车中读取数据
        if request.user.is_authenticated:
            redis_cli = get_redis_connection('carts')
            sku_cart_bytes = redis_cli.hgetall('cart_%s' % request.user.id)
            sku_cart_int = {int(sku_id): int(count) for sku_id, count in sku_cart_bytes.items()}
        else:
            cart_str = request.COOKIES.get('carts')
            if cart_str:
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                cart_dict = {}
            sku_cart_int = {}
            for sku_id, dict1 in cart_dict.items():
                sku_cart_int[sku_id] = dict1.get('count')
        # 查询商品对象
        skus = SKU.objects.filter(pk__in=sku_cart_int.keys())
        # 遍历，构造前端需要的数据结构
        sku_list = []
        for sku in skus:
            sku_list.append({
                'id': sku.id,
                'name': sku.name,
                'count': sku_cart_int.get(sku.id),
                'default_image_url': sku.default_image.url
            })

        # 响应
        return JsonResponse({
            'code': RETCODE.OK,
            'errmsg': "OK",
            'cart_skus': sku_list
        })
