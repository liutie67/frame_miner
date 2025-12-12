import cv2

class AppConfig:
    """
    应用程序全局配置类。
    存储颜色、按键映射、路径默认值等常量。
    """

    __version__ = '3.3.1'

    # 基础颜色定义 (BGR 格式)
    COLORS = {
        'red': (0, 0, 255),
        'green': (0, 255, 0),
        'blue': (255, 0, 0),
        'yellow': (0, 255, 255),
        'cyan': (255, 255, 0),
        'magenta': (255, 0, 255),
        'white': (255, 255, 255),
        'black': (0, 0, 0),
        'gray': (50, 50, 50),
        'light_gray': (200, 200, 200),
        'shadow': (0, 0, 0)
    }

    # 默认类别颜色映射 (按键字符 -> BGR)
    CLASS_COLORS = {
        'z': (0, 69, 255),    # 红
        'x': (0, 255, 0),     # 绿
        'c': (255, 165, 0),   # 蓝/橙
        'v': (0, 255, 255),   # 黄
        'b': (255, 255, 0),   # 青
        'n': (96, 164, 244),
        'm': (266, 43, 138),
        'default': (200, 200, 200)
    }

    # 基础按键定义
    BASE_KEYS = [ord('z'), ord('x'), ord('c'), ord('v'), ord('b'), ord('n'), ord('m'), ord('o')]
    BASE_CHARS = ['z', 'x', 'c', 'v', 'b', 'n', 'm', 'other']

    # 字体配置
    FONT = cv2.FONT_HERSHEY_SIMPLEX
    FONT_SCALE_TITLE = 1.5
    FONT_SCALE_NORMAL = 0.7