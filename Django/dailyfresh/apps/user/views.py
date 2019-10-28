import re

from django.conf import settings
from django.contrib.auth import authenticate, login, logout

from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.generic import View
from django.core.paginator import Paginator
from django_redis import get_redis_connection
from itsdangerous import SignatureExpired
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from user.models import User, Address
from goods.models import GoodsSKU
from order.models import OrderInfo, OrderGoods
from utils.mixin import LoginRequiredMixin

# from django.core.mail import send_mail
from celery_tasks.tasks import send_register_active_email


# Create your views here.

# /user/register
def register(request):
    """显示注册页面"""
    if request.method == 'GET':
        """显示注册页面"""
        return render(request, 'register.html')
    else:
        # 接受数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 进行数据校验
        if not all([username, password, email]):
            # 数据不完整
            return render(request, 'register.html', {'errmsg': "数据不完整"})

        # 1. 校验邮箱
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {"errmsg": "邮箱格式不正确"})

        if allow != 'on':
            return render(request, 'register.html', {'errmsg': "请同意协议"})
        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在
            user = None
        print(user)
        if user:
            return render(request, 'register.html', {'errmsg': "用户名已存在"})

        # 进行业务处理：进行用户注册
        """user = User()
        user.username = username
        user.save()"""
        user = User.objects.create_user(username, password, email)
        # 默认是不激活的
        user.is_active = 0
        user.save()

        # 返回应答,跳转到首页
        return redirect(reverse('goods:index'))


# /user/register_handle
def register_handle(request):
    """注册处理"""
    # 接受数据
    username = request.POST.get('user_name')
    password = request.POST.get('pwd')
    email = request.POST.get('email')
    allow = request.POST.get('allow')
    # 进行数据校验
    if not all([username, password, email]):
        # 数据不完整
        return render(request, 'register.html', {'errmsg': "数据不完整"})

    # 1. 校验邮箱
    if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
        return render(request, 'register.html', {"errmsg": "邮箱格式不正确"})

    if allow != 'on':
        return render(request, 'register.html', {'errmsg': "请同意协议"})
    # 校验用户名是否重复
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        # 用户名不存在
        user = None
    print(user)
    if user:
        return render(request, 'register.html', {'errmsg': "用户名已存在"})

    # 进行业务处理：进行用户注册
    """user = User()
    user.username = username
    user.save()"""
    user = User.objects.create_user(username, password, email)
    # 默认是不激活的
    user.is_active = 0
    user.save()

    # 返回应答,跳转到首页
    return redirect(reverse('goods:index'))


"""
    类视图
    不同请求方式，可以使用类视图
"""


class RegisterView(View):
    """注册"""

    def get(self, request):
        """显示注册页面"""
        return render(request, 'register.html')

    def post(self, request):
        """注册处理"""
        """注册处理"""
        # 接受数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        print("注册信息：\n\t用户名:{}\n\t密码：{}".format(username, password))
        # 进行数据校验
        if not all([username, password, email]):
            # 数据不完整
            return render(request, 'register.html', {'errmsg': "数据不完整"})

        # 1. 校验邮箱
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {"errmsg": "邮箱格式不正确"})

        if allow != 'on':
            return render(request, 'register.html', {'errmsg': "请同意协议"})
        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在
            user = None
        # print(user)
        if user:
            return render(request, 'register.html', {'errmsg': "用户名已存在"})

        # 进行业务处理：进行用户注册
        """user = User()
        user.username = username
        user.save()"""
        user = User.objects.create_user(username, password=password, email=email)
        # 默认是不激活的
        user.is_active = 0
        user.save()
        # print(user.password)
        # 发送激活邮件，包含激活链接：http:127.0.0.1:8000/user/active/3
        # 激活链接中需要包含用户的身份信息，并且要把身份信息加密处理
        # 直接将 id 信息放入链接中，不安全
        # 加密用户的身份信息，生成激活的token
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        # dumps() 返回的字节
        token = serializer.dumps(info)
        token = token.decode('utf-8')

        # 发邮件
        # subject = '天天生鲜欢迎信息'
        # messgae = ''  # message发送的内容不支持html解析
        # sender = settings.EMAIL_FROM
        # receiver = [email]
        # # 若是发送的正文内容包含 html代码，使用html_message参数
        # html_message = '<h1>%s，欢迎您注册天天生鲜会员</h1>请点击下面链接激活您的账户<br/> <a href = "http://127.0.0.1:8000/user/active/%s">http://120.0.0.1:8000/user/active/%s</a>' % (username, token, token)
        # # 如果由于各种原因，这封邮件发送所需时间较长，那么客户端将会等待很久，造成不好的用户体验.
        # send_mail(subject, messgae, sender, receiver, html_message=html_message)

        send_register_active_email.delay(email, username, token)
        # 返回应答,跳转到首页
        return redirect(reverse('goods:index'))


"""激活视图"""


class ActiveView(View):
    """用户激活"""

    def get(self, request, token):
        """进行用户激活"""
        # 进行解密，获取要激活的用户信息
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            # 获取待激活用户的id
            user_id = info['confirm']
            # 根据id获取用户信息
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()

            # 跳转到登录页面
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            # 激活链接已过期
            # 实际开发中，需要跳转到另一个页面，重新发送激活邮件
            return HttpResponse("激活链接已过期")


class LoginView(View):
    """登录"""

    def get(self, request):
        """显示登录页面"""
        # 判断是否记住了用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        return render(request, 'login.html', {'username': username, 'checked': checked})

    def post(self, request):
        """登录校验"""
        # 接受数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        print("登录信息：\n\t用户名:{}\n\t密码：{}".format(username, password))
        # 校验数据
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg': '数据不完整'})

        # 业务处理：登录校验
        user = authenticate(username=username, password=password)
        # print(user)
        if user is not None:
            # 用户名、密码正确
            if user.is_active:
                # 用户已激活
                login(request, user)

                # 获取登录后要跳转得到地址
                # 默认跳转到首页
                next_url = request.POST.get('next', reverse('goods:index'))
                # 跳转到next_url
                response = redirect(next_url)
                # 判断是否需要记住用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    # 记住用户名
                    response.set_cookie('username', username, max_age=7 * 24 * 3600)
                else:
                    response.delete_cookie('username')

                # 返回response
                return response
            else:
                # 用户未激活
                return render(request, 'login.html', {'errmsg': '账户未激活'})
        else:
            # Return an 'invalid login' error message.
            return render(request, 'login.html', {'errmsg': '用户名或密码错误'})
# /user/logout
class LogoutView(View):
    """退出登录"""
    def get(self,request):
        """跳转到登陆页面"""
        # 清除用户的session信息
        logout(request)

        # 跳转到首页
        return redirect(reverse('user:login'))


# /user
class UserInfoView(LoginRequiredMixin, View):
    '''用户中心-信息页面'''
    def get(self, request):
        """显示"""
        # request.user

        # 如果用户登录--> User的一个实例
        # 如果用户未登录 --> AnonymousUser类的一个实例
        # request.user.is_authenticated() 上述两个实例都有is_authecticated函数，User调用此方法返回的是True，另一个则是False

        # 获取用户的个人信息
        user = request.user
        address = Address.objects.get_default_address(user)

        # 获取用户的历史浏览记录
        # from redis import StrictRedis
        # sr = StrictRedis('192.168.1.102',db=10)
        con = get_redis_connection('default')
        history_key = 'history_%d' % user.id
        # 获取用户最新的浏览的5个商品的id
        sku_ids = con.lrange(history_key, 0, 4)
        print(sku_ids)
        # 从数据库中查询用户浏览的商品具体信息

        #####  问题：方式a和方式b哪种效率更高？  #####
        # 遍历用户浏览的商品信息
        # a. 双重循环实现方式
        # goods_li = GoodsSKU.objects.filter(id__in=sku_ids)
        #
        # goods_res = []
        # for id in sku_ids:
        #     for goods in goods_li:
        #         if id == goods.id:
        #             goods_res.append(goods)
        # b. 单次循环实现方式
        goods_res = []
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_res.append(goods)
        print(goods_res)
        # 除了你给模板文件变量之外，django框架会把request.user也传给模板文件
        context = {'page':'user',
                   'address':address,
                   "goods_res":goods_res}
        return render(request, 'user_center_info.html', context)


# /user/order
class UserOrderView(LoginRequiredMixin, View):
    '''用户中心-订单页面'''
    def get(self, request, page):
        """显示"""
        user = request.user
        # 获取用户的订单信息
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')
        # 遍历获取订单商品的信息
        for order in orders:
            # 查询订单商品信息
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)

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

        # 数据进行分页
        paginator = Paginator(orders, 1)

        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1
        if page > paginator.num_pages:
            page = 1

        # 获取第page页的Page实例对象
        order_page = paginator.page(page)

        # TODO: 页码控制，最多显示5个页码
        # 1. 总页码小于5页，显示所有页码
        # 2. 如果当前页是前3页，显示1-5页页码
        # 3. 如果当前页是后3页，显示后5页页码
        # 4. 其它情况，显示 “当前页前2页、当前页、后2页”
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        #组织上下文
        context = {
            'order_page':order_page,
            'pages':pages,
            'page': 'order',

        }
        return render(request, 'user_center_order.html', context)


# /user/address
class AddressView(LoginRequiredMixin, View):
    '''用户中心-地址页面'''
    def get(self, request):
        """显示"""

        # 获取用户默认收货地址
        # 获取登录用户
        user = request.user
        # a. 未使用模型管理器类
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     # 收货地址不存在
        #     address = None
        # b. 使用模型管理器类来简化代码
        address = Address.objects.get_default_address(user)
        return render(request, 'user_center_site.html', {'page':'address', 'address':address})

    def post(self, request):
        """地址添加"""
        # 接受数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        # 校验数据
            # 邮编作用不大，所以可为空
        if not all([receiver, addr, phone]):
            return render(request, 'user_center_site.html', {'errmsg':'数据不完整'})
        # 校验手机号
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$', phone):
            return  render(request, 'user_center_site.html', {'errmsg':"手机格式不正确"})


        # 业务处理：地址添加
        # 如果用户已存在默认收货地址，添加的地址不作为默认收货地址，否则就作为默认收货地址

        # 获取登录用户
        user = request.user
        # a. 未使用模型管理器类
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     # 收货地址不存在
        #     address = None

        # b. 使用模型管理器类来简化代码
        address = Address.objects.get_default_address(user)
        if address:
            is_default = False
        else:
            is_default = True

        # 添加地址
        Address.objects.create(user=user,
                               addr=addr,
                               receiver=receiver,
                               phone=phone,
                               zip_code=zip_code,
                               is_default=is_default)

        # 返回应答 刷新地址页面
        return redirect(reverse('user:address'))  # get请求方式


