import os
from datetime import datetime

from alipay import AliPay
from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import JsonResponse,HttpResponse
from django.shortcuts import render, redirect
from django.views.generic import View
from django_redis import get_redis_connection
from goods.models import GoodsSKU
from user.models import Address

from utils.mixin import LoginRequiredMixin
from .models import OrderInfo, OrderGoods


# Create your views here.


# /order/place
# 前端传递的参数：地址id，支付方式，购买的商品id
class OrderPlaceView(LoginRequiredMixin, View):
    """提交订单页面"""

    def post(self, request):
        """提交订单页面显示"""
        # 获取登录的用户
        user = request.user
        # 获取参数sku_ids
        sku_ids = request.POST.getlist('sku_ids')

        # 校验参数
        if not sku_ids:
            # 跳转到购物车页面
            return redirect(reverse('cart:show'))

        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        skus = []
        total_price = 0
        total_count = 0
        # 遍历sku_ids获取用户要购买的商品信息
        for sku_id in sku_ids:
            # 根据商品的id获取商品的信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 获取用户要购买商品的数量
            count = conn.hget(cart_key, sku_id)
            # 计算商品的小计
            amount = sku.price * int(count)
            # 动态给sku增加属性count，保存购买商品的数量
            sku.count = count
            sku.amount = amount
            skus.append(sku)

            # 累加计算商品的总件数和总价格
            total_count += int(count)
            total_price += amount

        # 运费：实际开发的时候，属于一个子系统
        transit_price = 10  # 运费

        # 实付款
        total_pay = total_price + transit_price

        # 获取用户的收件地址
        addrs = Address.objects.filter(user=user)

        # 组织上下文
        context = {
            'skus': skus,
            'total_count': total_count,
            'total_price': total_price,
            'transit_price': transit_price,
            'total_pay': total_pay,
            'addrs': addrs,
            'sku_ids':','.join(sku_ids)
        }
        # 使用模板
        return render(request, 'place_order.html', context)


# /order/commit
# 高并发 : 秒杀，出现问题 同一件商品被多次下单成功
# 解决方案：a. 悲观锁, b. 乐观锁
# 悲观锁：查询语句加锁
# 乐观锁：不加锁，在查询数据时不加锁，在更新时进行判断。
#   判断更新时地库存和之前查出地库存是否一致。
class OrderCommitView1(View):
    """订单创建"""
    @transaction.atomic
    def post(self, request):
        """订单创建"""
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            # 用户未登录
            return JsonResponse({'res':0, 'errmsg':"用户未登录"})

        # 接受参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        # 校验参数
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res':1, 'errmsg':"数据不完整"})

        # 校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res':2,'errmsg':"非法的支付方式"})

        # 校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist as e:
            return JsonResponse({'res':3,'errmsg':"地址非法"})

        # TODO: 创建订单核心业务
        # 组织参数
        # 订单id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)

        # 运费
        transit_price = 10

        # 总数目和总金额
        total_count = 0
        total_price = 0


        # 设置事务保存点
        save_id = transaction.savepoint()
        try:
            # TODO: 向df_order_info表中添加一条记录
            order = OrderInfo.objects.create(order_id=order_id,
                                             addr=addr,
                                             user=user,
                                             pay_method=pay_method,
                                             total_price=total_price,
                                             total_count=total_count,
                                             transit_price=transit_price)

            # TODO: 用户的订单中有几个商品，需要向df_order_goods表中添加几条记录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                try:
                    # 悲观锁，用于解决一件商品生成多个订单情况，即同一时刻有多人同时成功地对同一件商品下单
                    # select * from df_goods_sku where id=sku_id for update
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                except GoodsSKU.DoesNotExist as e:
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res':4,'errmsg':"商品不存在"})

                # 从redis中获取商品数量
                count = conn.hget(cart_key, sku_id)
                count = int(count)

                # TODO: 判断商品库存
                if count > sku.stock:
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res':5,'errmsg':"商品库存不足"})
                # TODO: 向df_order_goods表添加记录
                OrderGoods.objects.create(order=order,
                                          sku=sku,
                                          count=count,
                                          price=sku.price)

                # TODO：更新商品的库存和销量
                sku.stock -= count
                sku.sales += count
                sku.save()

                # TODO: 累加计算订单商品的总数量和总价格
                amount = sku.price * count
                total_count += count
                total_price += amount

            # TODO:更新订单信息表中的总数目和总价格
            order.total_price = total_price
            order.total_count = total_count
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res':7,'errmsg':'下单失败'})

        # 提交事务
        transaction.savepoint_commit(save_id)
        # TODO: 清除用户车购物车中的记录
        conn.hdel(cart_key, *sku_ids)

        # 返回应答
        return JsonResponse({'res':6,'message':"创建成功"})


class OrderCommitView(View):
    """订单创建"""

    @transaction.atomic
    def post(self, request):
        """订单创建"""
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            # 用户未登录
            return JsonResponse({'res': 0, 'errmsg': "用户未登录"})

        # 接受参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        # 校验参数
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': "数据不完整"})

        # 校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg': "非法的支付方式"})

        # 校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist as e:
            return JsonResponse({'res': 3, 'errmsg': "地址非法"})

        # TODO: 创建订单核心业务
        # 组织参数
        # 订单id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)

        # 运费
        transit_price = 10

        # 总数目和总金额
        total_count = 0
        total_price = 0
        i = 0

        # 设置事务保存点
        save_id = transaction.savepoint()
        try:
            # TODO: 向df_order_info表中添加一条记录
            order = OrderInfo.objects.create(order_id=order_id,
                                             addr=addr,
                                             user=user,
                                             pay_method=pay_method,
                                             total_price=total_price,
                                             total_count=total_count,
                                             transit_price=transit_price)

            # TODO: 用户的订单中有几个商品，需要向df_order_goods表中添加几条记录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                while i < 3:
                    try:
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except GoodsSKU.DoesNotExist as e:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 4, 'errmsg': "商品不存在"})

                    # 从redis中获取商品数量
                    count = conn.hget(cart_key, sku_id)
                    count = int(count)

                    # TODO: 判断商品库存
                    if count > sku.stock:
                        if i == 2:
                            transaction.savepoint_rollback(save_id)
                            return JsonResponse({'res': 5, 'errmsg': "商品库存不足"})
                        i += 1
                        continue

                    # TODO：更新商品的库存和销量
                    origin_stock = sku.stock
                    new_stock = origin_stock - count
                    new_sales = sku.sales + count

                    # update df_goods_sku set stock=new_stock, sales=new_sales
                    # where id=sku_id and stock=origin_stock
                    # 返回受影响地行数
                    res = GoodsSKU.objects.filter(id=sku_id,stock=origin_stock).update(stock=new_stock,sales=new_sales)
                    if res == 0:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 7, 'errmsg': '下单失败2'})

                    # TODO: 向df_order_goods表添加记录
                    OrderGoods.objects.create(order=order,
                                              sku=sku,
                                              count=count,
                                              price=sku.price)


                    # TODO: 累加计算订单商品的总数量和总价格
                    amount = sku.price * count
                    total_count += count
                    total_price += amount

                    break

            # TODO:更新订单信息表中的总数目和总价格
            order.total_price = total_price
            order.total_count = total_count
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})

        # 提交事务
        transaction.savepoint_commit(save_id)
        # TODO: 清除用户车购物车中的记录
        conn.hdel(cart_key, *sku_ids)

        # 返回应答
        return JsonResponse({'res': 6, 'message': "创建成功"})

# ajav post
# 前端传递的参数：订单id
class OrderPayView(View):
    """订单支付"""
    def post(self, request):
        """订单支付"""

        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            # 用户未登录
            return JsonResponse({'res': 0, 'errmsg': "用户未登录"})

        # 接收参数
        order_id = request.POST.get('order_id')



        # 校验参数
        if not order_id:
            return JsonResponse({'res':1,'errmsg':"无效的订单id"})

        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res':2,"errmsg":"订单错误"})

        # 业务处理：使用python sdk 调用支付宝支付接口

        # 初始化
        alipay = AliPay(
            appid="2016101300673547", # 应用id
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(settings.BASE_DIR,'apps/order/app_private_key.pem'),
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_path=os.path.join(settings.BASE_DIR,'apps/order/alipay_public_key.pem'),
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False 沙箱是True
        )
        # 调用支付接口
        # 电脑网站支付，需要跳转到https://openapi.alipay.com/gateway.do? + order_string
        # 沙箱地址 https://openapi.alipaydev.com/gateway.do? + order_string
        total_pay = order.total_price + order.transit_price  # Decimal类型
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,  # 订单id
            total_amount=str(total_pay),
            subject='天天生鲜%s'%order_id,
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )

        # 返回应答
        pay_url = '	https://openapi.alipaydev.com/gateway.do?' + order_string
        return JsonResponse({'res':3,"pay_url":pay_url})

# ajax post
# 传递参数：订单id
# /order/check
class OrderCheckView(View):
    """查询订单支付结果"""
    def post(self, request):
        """查询支付结果"""
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            # 用户未登录
            return JsonResponse({'res': 0, 'errmsg': "用户未登录"})

        # 接收参数
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': "无效的订单id"})

        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, "errmsg": "订单错误"})

            # 业务处理：使用python sdk 调用支付宝支付接口

            # 初始化
        alipay = AliPay(
            appid="2016101300673547",  # 应用id
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_path=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'),
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False 沙箱是True
        )

        # 调用支付宝的交易查询接口
        while True:
            response = alipay.api_alipay_trade_query(out_trade_no=order_id)
            # "alipay_trade_query_response": {
            #     "trade_no": "2017032121001004070200176844",  # 支付宝交易号
            #     "code": "10000",  # 接口是否调用成功
            #     "invoice_amount": "20.00",
            #     "open_id": "20880072506750308812798160715407",
            #     "fund_bill_list": [
            #         {
            #             "amount": "20.00",
            #             "fund_channel": "ALIPAYACCOUNT"
            #         }
            #     ],
            #     "buyer_logon_id": "csq***@sandbox.com",
            #     "send_pay_date": "2017-03-21 13:29:17",
            #     "receipt_amount": "20.00",
            #     "out_trade_no": "out_trade_no15",
            #     "buyer_pay_amount": "20.00",
            #     "buyer_user_id": "2088102169481075",
            #     "msg": "Success",
            #     "point_amount": "0.00",
            #     "trade_status": "TRADE_SUCCESS",  # 支付结果
            #     "total_amount": "20.00"
            # }

            code = response.get('code')
            print(code)
            trade_status = response.get('trade_status')
            print(trade_status)
            if code == '10000' and trade_status == 'TRADE_SUCCESS':
                # 支付成功
                # 获取支付宝交易号
                trade_no = response.get('trade_no')
                # 更新订单状态
                order.trade_no = trade_no
                order.order_status = 4 # 待评价
                order.save()
                # 返回结果
                return JsonResponse({'res':3,'message':"支付成功"})
            elif code == '40004' or (code == '10000' and trade_status == 'WAIT_BUYER_PAY'):
                # 等待买家付款
                # 业务处理失败，可能一会就会成功
                import time
                time.sleep(5)
                continue
            else:
                # 支付出错
                return JsonResponse({'res': 4, 'errmsg': "支付失败"})

# 地址栏传递参数：订单id
# /order/comment/order_id
class OrderCommentView(LoginRequiredMixin, View):
    """订单评价"""
    def get(self, request, order_id):
        """显示评价页面"""
        user = request.user
        # 获取用户的订单信息
        try:
            order = OrderInfo.objects.get(user=user, order_id=order_id)
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))
        # 查询订单商品信息
        order_skus = OrderGoods.objects.filter(order_id=order_id)

        # 遍历order_skus计算商品的小计
        for order_sku in order_skus:
            # 计算小计
            amount = order_sku.price * order_sku.count

            # 动态增加属性
            order_sku.amount = amount
        # 保存订单状态文字信息
        order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
        # 动态增加order的属性，保存订单商品的信息
        order.order_skus = order_skus


        return render(request, 'order_comment.html',{'order':order})

    def post(self, request, order_id):
        """处理评论内容"""
        # 获取数据
        user = request.user

        # 数据校验
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(user=user, order_id=order_id)
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))

        # 获取评论数据
        total_count = request.POST.get('total_count')
        total_count = int(total_count)

        for i in range(1,total_count+1):
            sku_id = request.POST.get('sku_%d' % i)
            comment = request.POST.get('content_%d' % i, '')
            try:
                order_goods = OrderGoods.objects.get(order=order,sku_id=sku_id)
            except OrderGoods.DoesNotExist:
                return redirect(reverse('user:order'))

            order_goods.comment = comment
            order_goods.save()

        order.order_status = 5
        order.save()

        return redirect(reverse('user:order',kwargs={'page':1}))
















