import os
import csv
import time
from pathlib import Path
import shutil

import cv2

class DataManager:
    """
    处理数据持久化、文件系统操作及历史记录管理。

    Attributes
    ----------
    save_dir : Path
        数据保存根目录。
    video_name : str
        视频文件名（不含后缀）。
    csv_path : Path
        CSV 标签文件路径。
    history_stack : list
        操作历史栈，用于撤回功能。
    global_marked_frames : dict
        内存中的标记缓存 {frame_id: label_short_code}。
    """

    def __init__(self, save_dir, video_name):
        """
        初始化数据管理器。

        Parameters
        ----------
        save_dir : str
            保存根路径。
        video_name : str
            视频名称。
        """
        self.output_root = Path(save_dir) / video_name
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.video_name = video_name
        self.csv_path = self.output_root / f"{video_name}_labels.csv"

        self.history_stack = []
        self.global_marked_frames = {}

        self._init_csv()
        self._load_existing_markers()

    def _init_csv(self):
        """初始化CSV文件，如果不存在则写入表头。"""
        if not self.csv_path.exists():
            with open(self.csv_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp_str', 'frame_id', 'timestamp_ms', 'class_label', 'note'])

    def _load_existing_markers(self):
        """读取已存在的CSV，填充 global_marked_frames 用于UI回显。"""
        if not self.csv_path.exists():
            return

        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                for row in reader:
                    if len(row) >= 4:
                        try:
                            f_id = int(row[1])
                            c_label = row[3]
                            # 提取简码 (class_z -> z)
                            short = c_label.split('_')[-1] if '_' in c_label else c_label
                            self.global_marked_frames[f_id] = short
                        except ValueError:
                            continue
            print(f"[DataManager] 已加载历史标记: {len(self.global_marked_frames)} 条")
        except Exception as e:
            print(f"[DataManager] 读取历史CSV警告: {e}")

    def save_record(self, frame_id, ms, label_long, label_short, mode, images_to_save):
        """
        保存一条标注记录（写入CSV并保存图片文件）。

        Parameters
        ----------
        frame_id : int
            帧号。
        ms : float
            时间戳(毫秒)。
        label_long : str
            完整类别名 (如 "class_car")。
        label_short : str
            简短代码 (如 "z")，用于UI颜色映射。
        mode : str
            采集模式 ('full' 或 'mark_only')。
        images_to_save : list of tuple
            待保存图片列表 [(image_data, suffix_name), ...]。
        """
        # 1. Update Memory
        self.global_marked_frames[frame_id] = label_short

        # 2. Write CSV
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        row_data = [time_str, frame_id, f"{ms:.2f}", label_long, mode]

        with open(self.csv_path, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(row_data)

        # 3. Save Images
        saved_files = []
        if mode == 'full':
            class_dir = self.output_root / label_long
            class_dir.mkdir(exist_ok=True)

            for img, fname_suffix in images_to_save:
                fname = f"{self.video_name}_{label_short}_{fname_suffix}.jpg"
                full_path = class_dir / fname
                # cv2.imwrite(str(full_path), img)  # cv2.imwrite() 经典路径包含汉字直接保存失败返回False， 但是无任何提示
                self.save_image_safe(full_path, img)  # 改为 imencode() 安全保存
                saved_files.append(full_path)

        # 4. Push to Stack
        self.history_stack.append({
            'files': saved_files,
            'csv_row': row_data,
            'frame_id': frame_id
        })

    def undo_last(self):
        """
        撤回最后一次操作。

        Returns
        -------
        bool
            撤回是否成功。
        """
        if not self.history_stack:
            return False

        last_record = self.history_stack.pop()

        # 1. Delete Files
        for p in last_record['files']:
            try:
                if p.exists():
                    os.remove(p)
            except Exception as e:
                print(f"删除文件失败: {e}")

        # 2. Remove from CSV (Read all -> Write all except last)
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            if len(lines) > 1:
                with open(self.csv_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines[:-1])
        except Exception as e:
            print(f"CSV回滚失败: {e}")
            return False

        # 3. Update Memory
        fid = last_record['frame_id']
        if fid in self.global_marked_frames:
            del self.global_marked_frames[fid]

        return True

    @staticmethod
    def save_image_safe(path, img, quality=95):
        """
        [Windows兼容性核心] 安全保存图片，支持中文路径。
        使用 numpy 先将图片编码为二进制流，再写入文件。

        Args:
            path (Path | str): 保存路径
            img (numpy.ndarray): 图像数据 (BGR)
            quality (int): JPEG/PNG 压缩质量 (0-100)

        Returns:
            bool: 是否保存成功
        """
        path = str(path)
        # 获取文件扩展名以决定编码格式
        ext = os.path.splitext(path)[1].lower()

        # 设置编码参数
        if ext in ['.jpg', '.jpeg']:
            params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        elif ext == '.png':
            # PNG 压缩级别 0-9，将 quality (0-100) 映射一下，通常默认即可
            params = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
        else:
            params = []

        try:
            # imencode 返回 (success, encoded_img)
            success, encoded_img = cv2.imencode(ext, img, params)
            if success:
                encoded_img.tofile(path)
                return True
            return False
        except Exception as e:
            print(f"保存图片失败: {e}")
            return False