from django.shortcuts import render
from django.views.generic import View
from mail.utils.categorys import get_category
from mail.utils.breadcrumb import get_breadcrumb
from django.http import HttpResponseForbidden,JsonResponse
from django.core.paginator import Paginator
from . import constants
from .models import GoodsCategory, GoodsChannel
from mail.utils.response_code import RETCODE
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
                hot_skus.append({'id': sku.id, 'default_image_url': sku.default_image.url, 'name': sku.name, 'price': sku.price})
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': RETCODE.DBERR, 'errmsg': 'error'})
        context = {
            'code': RETCODE.OK,
            'errmsg': 'OK',
            'hot_sku_list': hot_skus,
        }
        return JsonResponse(context)

