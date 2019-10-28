import pymysql

pymysql.install_as_MySQLdb()


class single(object):
    def __new__(cls, *args, **kwargs):
        cls.instance = None
        if cls.instance:
            cls.instance = super(single, cls).__new__()
            return cls.instance
        else:
            return cls.instance

    def __init__(self):
        pass

if __name__ == '__main__':
    s = single()
    print(id(s))
    s1 = single()
    print(id(s1))
