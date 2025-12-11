# frame_miner/__init__.py
"""
Frame Miner (视频数据标注工具包)
===============================

这是一个基于 OpenCV 的交互式视频数据采集与标注工具库。
专为构建目标检测 (YOLO) 或分类数据集设计。

主要功能
-------
1. **多类别采集**：支持自定义按键 (Z/X/C/V/B) 进行分类标注。
2. **回溯截取**：支持自动向前回溯截取多帧，防止错过关键动作。
3. **交互友好**：提供进度条回显、操作撤回 (Undo)、倍速播放等功能。
4. **数据管理**：自动生成结构化文件夹与 CSV 标签文件。

模块结构
-------
- `LabelingApp`: 应用程序主入口。
- `AppConfig`: 全局配置参数（颜色、按键映射）。
- `DataManager`: 负责 CSV/图片文件的读写与撤回。

使用示例
-------
>>> from frame_miner import LabelingApp
>>> # 初始化标注应用
>>> app = LabelingApp(
...     video_path="input_video.mp4",
...     save_dir="my_dataset",
...     class_names=["car", "bus", "bike"]
... )
>>> # 启动主循环
>>> app.run()

Authors
-------
LIU Tie (2025-12-11)
"""

# --- 下面才是代码导入部分 ---

from .main import LabelingApp
from .config import AppConfig

# 定义版本号
__version__ = config.AppConfig.__version__
__author__ = 'LIU Tie'

# 定义 'from video_tagger import *' 时导出的内容
__all__ = ['LabelingApp', 'AppConfig']
