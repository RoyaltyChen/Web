# 使用celery
# 在任务处理者一端加
import os

from celery import Celery
from django.conf import settings
from django.core.mail import send_mail
from django.template import loader

# 以下几行代码是加载了Django框架内容，否则无法导入模型类。
#import django
#os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dailyfresh.settings")
#django.setup()

from goods.models import GoodsType, IndexTypeGoodsBanner, IndexPromotionBanner, IndexGoodsBanner
# 创建一个Celery实例对象
# broker 指定redis数据库作为中间人，指定与数据库同台机器的redis中的8号数据库
# backend = 'redis://192.168.1.102:6379/8'
app = Celery('celery_tasks.tasks', broker='redis://192.168.1.102:6379/8')


# 定义任务函数
@app.task
def send_register_active_email(to_email, username, token):
    """发送激活邮件"""
    # 组织邮件信息
    subject = '天天生鲜欢迎信息'
    messgae = ''  # message发送的内容不支持html解析
    sender = settings.EMAIL_FROM
    receiver = [to_email]
    # 若是发送的正文内容包含 html代码，使用html_message参数
    html_message = '<h1>%s，欢迎您注册天天生鲜会员</h1>请点击下面链接激活您的账户<br/> <a href = "http://127.0.0.1:8000/user/active/%s">http://120.0.0.1:8000/user/active/%s</a>' % (
        username, token, token)
    # 如果由于各种原因，这封邮件发送所需时间较长，那么客户端将会等待很久，造成不好的用户体验.
    send_mail(subject, messgae, sender, receiver, html_message=html_message)
    # time.sleep(5)


@app.task
def generate_static_index_html():
    """产生首页静态页面"""
    # 获取商品的种类信息
    types = GoodsType.objects.filter(is_delete=False)

    # 获取首页轮播商品信息
    goods_banners = IndexGoodsBanner.objects.all().order_by('index')

    # 获取首页促销活动信息
    promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

    # 获取首页分类商品信息
    for t in types:  #
        # 获取每个商品种类首页分类商品的图片展示信息
        image_banners = IndexTypeGoodsBanner.objects.filter(type=t, display_type=1)
        # 获取每个商品种类首页分类商品的文字展示信息
        title_banners = IndexTypeGoodsBanner.objects.filter(type=t, display_type=0)

        # 动态增加types中每个类别t的属性，分别保存图片和文字展示信息
        t.image_banners = image_banners
        t.title_banners = title_banners

    # 组织上下文
    context = {
        'types': types,
        'goods_banners': goods_banners,
        'promotion_banners': promotion_banners,

    }

    # 使用模板
    # 1. 加载模板文件, 返回模板对象
    temp = loader.get_template('static_index.html')
    # 2. 定义模板上下文
    # RequestContext(request, context)
    # 3. 模板渲染
    static_index_html = temp.render(context)

    # 生成首页对应的静态文件
    save_path = os.path.join(settings.BASE_DIR, 'static/index.html')
    with open(save_path, 'w') as f:
        f.write(static_index_html)
