from datetime import datetime
from django.db import transaction
from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse, HttpResponseServerError, Http404
from django.core.paginator import Paginator
from mail.utils.login import LoginRequiredMixin
from users.models import Address
from django_redis import get_redis_connection
from goods.models import SKU
from mail.utils.response_code import RETCODE
from .models import OrderInfo, OrderGoods
import json
import logging

logger = logging.getLogger('django')


# Create your views here.

class OrderView(LoginRequiredMixin, View):

    def get(self, request):
        user = request.user
        try:
            address = user.addresses.filter(is_deleted=False)
        except Address.DoesNotExist:
            address = None
        redis_conn = get_redis_connection('carts')
        cart_selected_bytes = redis_conn.smembers('selected_%s' % user.id)
        cart_selected_int = {int(sku_id) for sku_id in cart_selected_bytes}

        cart_skus_bytes = redis_conn.hgetall('cart_%s' % user.id)
        cart_skus_int = {int(sku_id): int(count) for sku_id, count in cart_skus_bytes.items()}

        skus = SKU.objects.filter(pk__in=cart_selected_int)
        cart_list = []
        total_order_amount = 0
        payment_amount = 0
        total_count = 0
        transfer_amount = 10
        for sku in skus:
            count = cart_skus_int.get(sku.id)
            amount = sku.price * count
            cart_list.append({
                'id': sku.id,
                'count': count,
                'price': str(sku.price),
                'default_image_url': sku.default_image.url,
                'name': sku.name,
                'amount': amount,
                'total_amount': amount
            })
            total_count += count
            total_order_amount += amount

        payment_amount = total_order_amount + transfer_amount
        context = {
            'addresses': address,
            'sku_list': cart_list,
            'total_amount': total_order_amount,
            'total_count': total_count,
            'transit': transfer_amount,
            'payment_amount': payment_amount
        }
        return render(request, 'place_order.html', context=context)


class OrderCommitView(LoginRequiredMixin, View):

    def post(self, request):
        json_dict = json.loads(request.body.decode())
        address_id = json_dict.get('address_id')
        print(address_id)
        pay_method = json_dict.get('pay_method')
        if not all([address_id, pay_method]):
            return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '缺少必需参数'})
        try:
            address = Address.objects.get(id=address_id, is_deleted=False, user_id=request.user.id)
        except Exception as e:
            return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '无效地址编号'})
        if pay_method not in [1, 2]:
            return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '无效支付方式'})
        user = request.user
        now = datetime.now()

        redis_conn = get_redis_connection('carts')
        cart_selected_bytes = redis_conn.smembers('selected_%s' % user.id)
        cart_selected_int = {int(sku_id) for sku_id in cart_selected_bytes}

        cart_skus_bytes = redis_conn.hgetall('cart_%s' % user.id)
        cart_skus_int = {int(sku_id): int(count) for sku_id, count in cart_skus_bytes.items()}

        with transaction.atomic():  # 禁止自动提交
            # 开启事务
            sid = transaction.savepoint()

            # 2.创建订单基本对象
            order_id = '%s%09d' % (now.strftime('%Y%m%d%H%M%S'), user.id)
            total_count = 0
            total_amount = 0
            transit = 10
            if pay_method == '1':
                # 待发货
                status = OrderInfo.ORDER_STATUS_ENUM['UNSEND']
            else:
                # 待支付
                status = OrderInfo.ORDER_STATUS_ENUM['UNPAID']

            order = OrderInfo.objects.create(
                order_id=order_id,
                user = user,
                address = address,
                total_count=total_count,
                total_amount=total_amount,
                freight=transit,
                pay_method=pay_method,
                status=status
            )

            skus = SKU.objects.filter(pk__in=cart_selected_int)

            for sku in skus:
                cart_count = cart_skus_int.get(sku.id)
                if cart_count > sku.stock:
                    transaction.savepoint_rollback(sid)
                    # 给出提示
                    return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '商品[%d]库存不足' % sku.id})
                # sku.stock -= cart_count
                # sku.sales += cart_count
                # sku.save()

                stock_old = sku.stock
                stock_new = sku.stock - cart_count
                sales_new = sku.sales + cart_count
                result = SKU.objects.filter(pk=sku.id, stock=stock_old).update(stock=stock_new, sales=sales_new)
                # result表示sql语句修改数据的个数
                if result == 0:
                    # 库存发生变化，未成功购买
                    transaction.savepoint_rollback(sid)
                    return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '服务器忙，请稍候重试'})
                # 修改SPU销量
                sku.spu.sales += cart_count
                sku.spu.save()
                OrderGoods.objects.create(
                    order=order,
                    sku=sku,
                    count=cart_count,
                    price=sku.price,

                )
                total_count += cart_count
                total_amount += sku.price * cart_count
            order.total_count = total_count
            order.total_amount = total_amount + 10
            order.save()
            transaction.savepoint_commit(sid)
        redis_conn.hdel('cart_%s' % user.id, *cart_selected_int)
        redis_conn.srem('selected_%s' % user.id, *cart_selected_int)

        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'order_id': order_id})


class OrderSuccessView(LoginRequiredMixin, View):

    def get(self, request):
        # 接收
        order_id = request.GET.get('order_id')
        payment_amount = request.GET.get('payment_amount')
        pay_method = request.GET.get('pay_method')

        context = {
            'order_id': order_id,
            'payment_amount': payment_amount,
            'pay_method': pay_method
        }

        return render(request, 'order_success.html', context)


class OrderInfoView(LoginRequiredMixin, View):

    def get(self, request, page_num):
        orders = request.user.orderinfo_set.order_by('-create_time')
        p = Paginator(orders, 2)
        try:
            page = p.page(page_num)
        except Exception as e:
            logger.error(e)
            return HttpResponseServerError('异常，请重试')
        page_list = []
        for order in page:
            detail_list = []
            for order_good in order.skus.all():
                detail_list.append({
                    'default_image_url': order_good.sku.default_image.url,
                    'name': order_good.sku.name,
                    'price': order_good.price,
                    'count': order_good.count,
                    'total_amount': order_good.price * order_good.count
                })

            page_list.append({
                'create_time': order.create_time,
                'order_id': order.order_id,
                'total_amount': order.total_amount,
                'freight': order.freight,
                'details': detail_list,
                'status': order.status
            })

        context = {
            'page': page_list,
            'page_num': page_num,
            'total_page': p.num_pages
        }
        return render(request, 'user_center_order.html', context=context)


class CommentView(LoginRequiredMixin, View):

    def get(self, request):
        order_id = request.GET.get('order_id')
        try:
            # 使用user_id的原因是订单编号会显示在地址栏，防止用户手动输入订单编号，评价别人订单，  使用user_id使用户只能评价自己的订单
            order = OrderInfo.objects.get(pk=order_id, user_id=request.user.id)
        except:
            return Http404('商品编号无效')

        # 获取订单的所有商品
        skus = []
        # detail表示OrderGoods类型的对象
        for detail in order.skus.filter(is_commented=False):
            skus.append({
                'sku_id': detail.sku.id,
                'default_image_url': detail.sku.default_image.url,
                'name': detail.sku.name,
                'price': str(detail.price),
                'order_id': order_id
            })

        context = {
            'skus': skus
        }
        return render(request, 'goods_judge.html', context)

    def post(self, request):
        # 接收
        data = json.loads(request.body.decode())
        order_id = data.get('order_id')
        sku_id = data.get('sku_id')
        comment = data.get('comment')
        score = data.get('score')
        is_anonymous = data.get('is_anonymous')

        # 验证
        if not all([order_id, sku_id, comment, score]):
            return JsonResponse({
                'code': RETCODE.PARAMERR,
                'errmsg': '参数不完整'
            })

        if not isinstance(is_anonymous, bool):
            return JsonResponse({
                'code': RETCODE.PARAMERR,
                'errmsg': '参数错误'
            })
        try:
            # 查询OrderGoods对象
            order_goods = OrderGoods.objects.get(order_id=order_id, sku_id=sku_id)
            order_goods.comment = comment
            order_goods.score = int(score)
            order_goods.is_anonymous = is_anonymous
            order_goods.is_commented = True
            order_goods.save()
            sku = SKU.objects.get(id=sku_id)

            # 累计评论数据
            sku.comments += 1
            sku.save()
            sku.spu.comments += 1
            sku.spu.save()

            # 判断订单商品是否都已经评价，如果是，修改订单状态为已完成
            if OrderGoods.objects.filter(order_id=order_id, is_commented=False).count() == 0:
                OrderInfo.objects.filter(order_id=order_id).update(status=OrderInfo.ORDER_STATUS_ENUM['FINISHED'])
        except Exception as e:
            logger.error(e)
            return JsonResponse({
                'code': RETCODE.DBERR,
                'errmsg': '出现异常'
            })

        return JsonResponse({
            'code': RETCODE.OK,
            'errmsg': 'OK'
        })


class GoodsCommentView(View):

    def get(self, request, sku_id):
        try:
            order_goods = OrderGoods.objects.filter(sku_id=sku_id, is_commented=True)
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': RETCODE.DBERR, 'errmsg': '异常，请重试'})
        comment_list = list()
        for good in order_goods:
            username = good.order.user.username
            if good.is_anonymous:
                username = '****'
            comment_list.append({
                'username': username,
                'comment': good.comment,
                'score': good.score
            })

        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'goods_comment_list': comment_list})

