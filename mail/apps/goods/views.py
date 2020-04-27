import datetime
import json
from django.shortcuts import render
from django.views.generic import View
from mail.utils.categorys import get_category
from mail.utils.breadcrumb import get_breadcrumb
from django.http import HttpResponseForbidden, JsonResponse, HttpResponseServerError
from django.core.paginator import Paginator
from . import constants
from .models import GoodsCategory, GoodsChannel, SKU, GoodsVisitCount
from mail.utils.response_code import RETCODE
from django_redis import get_redis_connection
import logging

logger = logging.getLogger('django')


# Create your views here.


class ListView(View):

    def get(self, request, category_id, page_num):
        sort = request.GET.get('sort')
        try:
            categorys = get_category()
            cat = GoodsCategory.objects.get(id=category_id)
            breadcrumb = get_breadcrumb(cat)
            if sort == 'hot':
                sort_field = '-sales'
            elif sort == 'price':
                sort_field = '-price'
            else:
                sort = 'default'
                sort_field = 'create_time'
            skus = cat.sku_set.filter(is_launched=True).order_by(sort_field)
            p = Paginator(skus, constants.GOODS_PAGE_LIMIT)
            page_skus = p.page(page_num)
        except Exception as e:
            logger.error(e)
            return render(request, '404.html')

        total_page = p.num_pages
        context = {
            'categories': categorys,
            'breadcrumb': breadcrumb,
            'category': cat,
            'sort': sort,
            'page_skus': page_skus,
            'page_num': page_num,
            'total_page': total_page,
        }
        return render(request, 'list.html', context=context)


class HotView(View):
    def get(self, request, category_id):
        sort = request.GET.get('sort')
        try:
            cat = GoodsCategory.objects.get(id=category_id)
            skus = cat.sku_set.filter(is_launched=True).order_by('-sales')[0:2]
            hot_skus = []
            for sku in skus:
                hot_skus.append(
                    {'id': sku.id, 'default_image_url': sku.default_image.url, 'name': sku.name, 'price': sku.price})
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': RETCODE.DBERR, 'errmsg': 'error'})
        context = {
            'code': RETCODE.OK,
            'errmsg': 'OK',
            'hot_sku_list': hot_skus,
        }
        return JsonResponse(context)


class DetailView(View):

    def get(self, request, sku_id):
        try:
            sku = SKU.objects.get(id=sku_id)
            spu = sku.spu
            cat3 = sku.category
            breadcrumb = get_breadcrumb(cat3)
            categories = get_category()
            specs = spu.specs.order_by('id')
            skus = spu.skus.order_by('id')
            sku_options = {}
            sku_option = []
            for sku1 in skus:
                infos = sku1.specs.order_by('spec_id')
                option_key = []
                for info in infos:
                    option_key.append(info.option_id)
                    # 获取当前商品的规格信息
                    if sku.id == sku1.id:
                        sku_option.append(info.option_id)
                sku_options[tuple(option_key)] = sku1.id

            # 遍历当前spu所有的规格
            specs_list = []
            for index, spec in enumerate(specs):
                option_list = []
                for option in spec.options.all():
                    # 如果当前商品为蓝、64,则列表为[2,3]
                    sku_option_temp = sku_option[:]
                    # 替换对应索引的元素：规格的索引是固定的[1,3]
                    sku_option_temp[index] = option.id
                    # 为选项添加sku_id属性，用于在html中输出链接
                    option.sku_id = sku_options.get(tuple(sku_option_temp), 0)
                    # 添加选项对象
                    option_list.append(option)
                # 为规格对象添加选项列表
                spec.option_list = option_list
                # 重新构造规格数据
                specs_list.append(spec)
        except Exception as e:
            logger.error(e)
            return HttpResponseServerError('出现异常')
        context = {
            'categories': categories,
            'breadcrumb': breadcrumb,
            'sku': sku,
            'spu': spu,
            'category_id': cat3.id,
            'specs': specs_list
        }
        return render(request, 'detail.html', context=context)


class DetailVisitView(View):
    def post(self, request, category_id):
        try:
            category = GoodsCategory.objects.get(id=category_id)
        except Exception as e:
            logger.error(e)
            return HttpResponseForbidden('缺少传入参数')
        date = datetime.datetime.now()
        today_str = '%d-%02d-%02d' % (date.year, date.month, date.day)
        today_date = datetime.datetime.strptime(today_str, '%Y-%m-%d')
        try:
            visit_count_object = category.goodsvisitcount_set.get(date=today_date)
        except Exception as e:
            logger.info(e)
            visit_count_object = GoodsVisitCount()
        try:
            visit_count_object.category = category
            visit_count_object.count += 1
            visit_count_object.save()
        except Exception as e:
            logger.error(e)
            return HttpResponseServerError('出现异常')

        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})


class HistoryView(View):

    def post(self, request):
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')
        if not sku_id:
            return JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '商品编号不存在'})
        if not request.user.is_authenticated:
            return JsonResponse({'code': RETCODE.USERERR, 'errmsg': '用户未登录，不记录浏览记录'})
        try:
            sku = SKU.objects.get(id=sku_id)
            redis_conn = get_redis_connection('history')
            # 创建管道，减少与redis交互次数，提高服务端利用率，增加效率
            pipe_line = redis_conn.pipeline()
            pipe_line.lrem('history_%s' % request.user.id, 0, sku_id)
            pipe_line.lpush('history_%s' % request.user.id, sku_id)
            pipe_line.ltrim('history_%s' % request.user.id, 0, 4)
            pipe_line.execute()
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': RETCODE.DBERR, 'errmsg': '记录失败'})

        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})

    def get(self, request):
        try:
            redis_conn = get_redis_connection('history')
            sku_ids = redis_conn.lrange('history_%s' % request.user.id, 0, -1)
            skus = []
            for sku_id in sku_ids:
                sku = SKU.objects.get(id=sku_id)
                skus.append({
                    'id': sku.id,
                    'name': sku.name,
                    'default_image_url': sku.default_image.url,
                    'price': sku.price
                })
        except Exception as e:
            return JsonResponse({'code': RETCODE.DBERR, 'errmsg': '查找浏览记录失败'})

        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'skus': skus})


