from pathlib import Path
import cv2
import time
import ctypes
import platform
import shutil

from .config import AppConfig
from .data_manager import DataManager
from .renderer import UIRenderer
from .video_controller import VideoController


def set_window_title_utf8(opencv_window_id, new_title):
    """
    强制设置 OpenCV 窗口标题支持中文 (仅限 Windows)

    :param opencv_window_id: cv2.namedWindow 创建时用的英文 ID
    :param new_title: 你想要显示的中文标题
    """
    if platform.system() != 'Windows':
        return  # Mac/Linux 通常原生支持 UTF-8，无需此操作

    try:
        # 1. 获取窗口句柄 (HWND)
        # FindWindowW 支持 Unicode
        hwnd = ctypes.windll.user32.FindWindowW(None, opencv_window_id)

        if hwnd:
            # 2. 设置新标题
            # SetWindowTextW 支持 Unicode
            ctypes.windll.user32.SetWindowTextW(hwnd, new_title)
    except Exception as e:
        print(f"设置中文标题失败: {e}")


class LabelingApp:
    """
    主应用程序控制器。

    Parameters
    ----------
    video_path : str
        视频文件的路径。
    save_dir : str, optional
        数据保存根目录。最终结构为: save_dir / 视频名 / class_x / 图片.jpg
    extract_num : int, optional
        向前回溯截取的数量。
        例如 extract_num=3, interval=5, 当前帧100:
        截取帧为 [85, 90, 95, 100]。
    interval : int, optional
        截取间隔帧数。
    mode : {'full', 'mark_only'}, optional
        'full': 记录 CSV 并保存图片。
        'mark_only': 仅记录 CSV。
    class_names : list, optional
        待分类型的名称，最多支持8种。按输入顺序映射到z, x, c, v, b, n, m, o(other)
    """

    def __init__(self, video_path, save_dir, class_names, extract_num=5, interval=5, mode='full'):
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Missing video file {video_path}")

        # 1. Init Modules
        self.video = VideoController(video_path)
        self.data = DataManager(save_dir, self.video.name)

        # 2. Config & Maps
        self.cfg = AppConfig()
        self.extract_num = extract_num
        self.interval = interval
        self.namedWindow = f'Multi-Class Object-Containing Frame Miner'
        self.dispaly_title = f'{self.namedWindow} <{video_path.name}>'
        self.mode = mode

        self.key_map = {}
        safe_names = class_names[:7] if class_names else []
        for i, code in enumerate(AppConfig.BASE_KEYS):
            name = safe_names[i] if i < len(safe_names) else AppConfig.BASE_CHARS[i]
            self.key_map[code] = name

        self.renderer = UIRenderer(self.key_map, class_names)

        # 3. State
        self.paused = False
        self.speed = 1.0
        self.running = True
        self.ui_msg = ""
        self.ui_msg_end = 0

    def run(self):
        """启动主循环"""
        self._show_intro()

        while self.running:
            # 1. Prepare Frame
            if not self.paused:
                ret, frame = self.video.read()
                if not ret:
                    self.running = False
                    break
            else:
                frame = self.video.frame_cache
                if frame is None: break

            # 2. Prepare UI State
            curr_idx = self.video.current_frame_idx
            is_marked = curr_idx in self.data.global_marked_frames

            # Check message timeout
            if self.ui_msg and self.ui_msg_end != -1 and time.time() > self.ui_msg_end:
                self.ui_msg = ""

            ui_state = {
                'curr_pos': curr_idx,
                'total_frames': self.video.total_frames,
                'speed': self.speed,
                'paused': self.paused,
                'markers': self.data.global_marked_frames,
                'is_marked': is_marked,
                'marker_label': self.data.global_marked_frames.get(curr_idx, ""),
                'ui_message': self.ui_msg
            }

            # 3. Render
            display_img = self.renderer.draw_interface(frame, ui_state)
            cv2.imshow(self.namedWindow, display_img)

            # 4. Input Handling
            self._handle_input()

        self.cleanup()

    def _handle_input(self):
        delay = 0 if self.paused else int(1000 / (self.video.fps * self.speed))
        key = cv2.waitKey(max(0, delay)) & 0xFF

        if key == 27:  # ESC
            self.running = False
        elif key == 32:  # Space
            self.paused = not self.paused
        elif key == ord('1'):
            self.speed = 1.0
        elif key == ord('2'):
            self.speed = 2.0
        elif key == ord('3'):
            self.speed = 3.0
        elif key == ord('5'):
            self.speed = 0.5
        elif key in self.key_map:
            self._handle_tagging(key)
        elif key == 8 and self.paused:  # Backspace
            if self.data.undo_last():
                self._set_msg("UNDO SUCCESSFUL", 2)
            else:
                self._set_msg("NOTHING TO UNDO", 1)
        elif self.paused and (key == ord('d') or key == ord('f')):
            # d (后退): 想看上一帧，就是 current - 1
            # f (前进): 想看下一帧，就是 current + 1
            if key == ord('d'):
                target_pos = max(0, self.video.current_frame_idx - 1)
                self.video.seek(target_pos)
            else:  # key == 'f'
                target_pos = self.video.current_frame_idx + 1
                self.video.seek(target_pos)

        # ... Add speed controls 1/2/3 here ...

    def _handle_tagging(self, key):
        """处理标记逻辑"""
        label = self.key_map[key]
        # Find short code for color mapping (e.g. 'z')
        short_code = 'default'
        idx = AppConfig.BASE_KEYS.index(key)
        if idx >= 0: short_code = AppConfig.BASE_CHARS[idx]

        curr_idx = self.video.current_frame_idx

        # Capture frames Logic
        images = []
        # Snapshot current pos
        backup_pos = curr_idx

        # Extract previous frames
        for i in range(-self.extract_num, 1):
            target = curr_idx + (i * self.interval)
            if 0 <= target < self.video.total_frames:
                self.video.seek(target)
                if self.video.frame_cache is not None:
                    images.append((self.video.frame_cache.copy(), f"{target:06d}"))

        # Restore pos
        self.video.seek(backup_pos)

        # Save
        self.data.save_record(
            curr_idx, self.video.get_ms(), f"class_{label}", short_code, self.mode, images
        )

        self._set_msg(f"SAVED [{label.upper()}]", 2)

        # Auto pause on tag?
        # self.paused = True

    def _set_msg(self, text, duration):
        self.ui_msg = text
        self.ui_msg_end = time.time() + duration if duration > 0 else -1

    def _show_intro(self):
        print("Press Space to start...")

        cv2.namedWindow(self.namedWindow, cv2.WINDOW_NORMAL)
        set_window_title_utf8(self.namedWindow, self.dispaly_title)

        print(f"----- 启动采集 V{self.cfg.__version__} : {self.video.name} -----")
        print(f"保存路径: {self.data.output_root}")
        print("---------------------------------------------------------")
        print("【当前按键映射】")
        for i, key_code in enumerate(self.cfg.BASE_KEYS):
            label = self.key_map[key_code]
            print(f"  按键 '{self.cfg.BASE_CHARS[i]}' -> 类别: {label}")
        print("---------------------------------------------------------")
        print("【播放控制】 空格: 暂停/继续 | 1/2/3/5(0.5倍): 切换倍速")
        print("【退出程序】 ESC")
        print("---------------------------------------------------------")

        ret, frame = self.video.read()
        if not ret: return
        self.video.frame_cache = frame

        # 1. 制作开场引导画面
        intro_frame = self.video.frame_cache.copy()
        h, w = intro_frame.shape[:2]

        # 提示语 (OpenCV默认不支持中文，使用英文替代)
        # "Hit Z/X/C/V/B at the LAST frame!"
        # "(Press SPACE to Start)"
        msg_title = "Hit [Z]/[X]/[C]/[V]/[B]/[N]/[M] at the LAST frame you can see object!"
        msg_sub = "(Switch Input Method to ENG! & Press [SPACE] to Start)"

        font = cv2.FONT_HERSHEY_SIMPLEX

        # 计算文字大小以居中
        (w_title, h_title), _ = cv2.getTextSize(msg_title, font, self.cfg.FONT_SCALE_TITLE, 3)
        (w_sub, h_sub), _ = cv2.getTextSize(msg_sub, font, 1.0, 2)

        x_title = (w - w_title) // 2
        x_sub = (w - w_sub) // 2
        y_center = h // 2

        # 绘制文字: 阴影(黑色) + 本体(亮色) 实现高对比度
        # 标题 (亮黄色)
        cv2.putText(intro_frame, msg_title, (x_title + 2, y_center - 10 + 2), font, self.cfg.FONT_SCALE_TITLE, (0, 0, 0), 3)  # 阴影
        cv2.putText(intro_frame, msg_title, (x_title, y_center - 10), font, self.cfg.FONT_SCALE_TITLE, (0, 255, 255), 3)  # 本体

        # 副标题 (亮绿色)
        cv2.putText(intro_frame, msg_sub, (x_sub + 2, y_center + 50 + 2), font, 1.0, (0, 0, 0), 2)  # 阴影
        cv2.putText(intro_frame, msg_sub, (x_sub, y_center + 50), font, 1.0, (0, 255, 0), 2)  # 本体

        cv2.imshow(self.namedWindow, intro_frame)

        # while True:
        #     k = cv2.waitKey(0) & 0xFF
        #     if k == 32: break
        #     if k == 27:
        #         self.running = False
        #         break

        # 2. 等待开始逻辑
        print(">>> [就绪] 请按空格键开始播放...")
        while True:
            start_key = cv2.waitKey(0) & 0xFF
            if start_key == 32:  # Space
                break
            elif start_key == 27:  # ESC
                self.cleanup()
                return

    def rebuild_dataset(self, new_save_dir, new_extract_num, new_interval, copy_csv=True):
        """
        根据现有的标记，使用新的参数（回溯帧数、间隔）重新生成图片数据集。

        Parameters
        ----------
        new_save_dir : str or Path
            新的数据集保存根目录。
        new_extract_num : int
            新的向前回溯截取数量。
        new_interval : int
            新的截取间隔帧数。
        copy_csv : bool, default True
            是否将原始的标签CSV文件复制到新目录。
        """

        # 1. 路径准备
        new_root = Path(new_save_dir) / self.video.name   # if new_save_dir == save_dir 会报错
        new_root.mkdir(parents=True, exist_ok=True)
        print(f"\n=== 开始重构数据集 ===")
        print(f"源视频: {self.video.name}")
        print(f"目标目录: {new_root}")
        print(f"参数变更: extract {self.extract_num}->{new_extract_num}, interval {self.interval}->{new_interval}")

        # 2. 获取所有已标记的帧 (从 DataManager 中获取)
        # 格式: {frame_id: 'short_code'} (例如 {150: 'z'})
        markers = self.data.global_marked_frames

        if not markers:
            print("⚠️ 当前没有加载任何标记，无法重构。请先运行程序或确保CSV已加载。")
            return

        # 3. 复制 CSV 文件 (如果需要)
        if copy_csv and self.data.csv_path.exists():
            new_csv_path = new_root / self.data.csv_path.name
            shutil.copy2(self.data.csv_path, new_csv_path)
            print(f"已复制 CSV 到: {new_csv_path}")

        # 4. 优化：按帧号排序
        # 视频 Seek 是很慢的操作，按顺序读取比跳来跳去快得多
        sorted_marker_items = sorted(markers.items(), key=lambda x: x[0])
        total_markers = len(sorted_marker_items)

        print(f"共需处理 {total_markers} 个标记点...")

        # 5. 遍历重构
        for idx, (center_frame_id, short_code) in enumerate(sorted_marker_items):
            # (A) 解析类别名，用于创建文件夹
            # 我们需要从 short_code ('z') 反查出 long_name ('class_car')
            # 这里的逻辑依赖于你之前的 key_map 结构
            label_long_name = "unknown"

            # 尝试查找对应的完整名称
            # 假设 short_code 是 'z'，我们要找 key_map 中对应的 value
            # 注意：这里需要你根据实际的 key_map 结构微调
            # 如果 key_map 是 {ord('z'): 'car'}, 我们需要反推
            found_name = False
            for k_code, k_name in self.key_map.items():
                # 将 ASCII 码转为字符对比 (如 122 -> 'z')
                # 或者如果 short_code 是 'default'
                k_char = chr(k_code).lower() if k_code < 256 else '?'
                if k_char == short_code:
                    label_long_name = f"class_{k_name}"
                    found_name = True
                    break

            if not found_name:
                # 如果没找到映射（比如是旧数据），直接用 code
                label_long_name = f"class_{short_code}"

            # (B) 创建分类子文件夹
            class_dir = new_root / label_long_name
            class_dir.mkdir(exist_ok=True)

            # (C) 计算新的目标帧列表
            # range(-new, 1) -> 生成 -5, -4, ... 0
            target_offsets = range(-new_extract_num, 1)
            target_frames = []
            for i in target_offsets:
                # 只有当 i 是 new_interval 的倍数或者是0时才取？
                # 不，逻辑是：每隔 new_interval 取一帧
                # 原逻辑: f_idx = curr_pos + (i * interval)
                f_idx = (center_frame_id - 1) + (i * new_interval)
                if 0 <= f_idx < self.video.total_frames:
                    target_frames.append(f_idx)

            # (D) 读取并保存
            for t_frame in target_frames:
                # 这是一个耗时操作
                self.video.seek(t_frame)
                ret, img = self.video.read()  # 这里注意 VideoController.read 返回 (ret, frame)

                if ret and img is not None:
                    # 文件名格式: VideoName_ShortCode_FrameID.jpg
                    fname = f"{self.video.name}_{short_code}_{t_frame:06d}.jpg"
                    save_path = class_dir / fname

                    # 只有文件不存在时才写入，避免重复 IO
                    if not save_path.exists():
                        # cv2.imwrite(str(save_path), img)
                        self.data.save_image_safe(str(save_path), img)

            # 简单的进度打印
            if (idx + 1) % 10 == 0:
                print(f"进度: {idx + 1}/{total_markers} 完成")

        print("=== 数据集重构完成 ===")

    def cleanup(self):
        self.video.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    app = LabelingApp(r"C:\video.mp4", "dataset", ['kilometer', 'hectometer', 'camera', 'white kilometer', 'point kilometrique', 'tunnel kilometer', 'tunnel hectometer'])
    app.run()