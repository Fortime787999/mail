from django_redis import get_redis_connection
import pickle
import base64


def merge_cart(request, response):
    cart_str = request.COOKIES.get('carts')
    if not cart_str:
        # cookie中没有购物车数据
        return response
    cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))

    # 向redis中保存购物车数据
    user = request.user
    redis_conn = get_redis_connection('carts')
    redis_pipeline = redis_conn.pipeline()
    for sku_id, sku_dict in cart_dict.items():
        # hash，存商品编号、数量
        redis_pipeline.hset('cart_%s' % user.id, sku_id, sku_dict.get('count'))
        # set，表示商品选中状态
        if sku_dict.get('selected'):
            redis_pipeline.sadd('selected_%s' % user.id, sku_id)
    redis_pipeline.execute()

    # 删除cookie中的购物车数据
    response.delete_cookie('carts')
    # 返回响应对象，最终返回给浏览器
    return response