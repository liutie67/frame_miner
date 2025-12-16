import csv
import ast
import time
from pathlib import Path
from typing import Union, List, Optional
import shutil
from collections import defaultdict

from frame_miner.main import LabelingApp


class ProjectManager:
    """
    批量视频处理与项目配置管理器。

    负责：
    1. 扫描源文件夹中的视频。
    2. 管理项目级的配置（CSV持久化），确保同一项目的标注标准（类别、参数）一致。
    3. 调度 LabelingApp 处理单个视频。
    """

    # 支持的视频扩展名
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.flv'}

    def __init__(self,
                 source_dir: Union[str, Path],
                 save_dir: Union[str, Path] = './dataset',
                 class_names: List[str] = None,
                 extract_num: int = 5,
                 interval: int = 5,
                 mode='mark_only'):
        """
        初始化项目管理器。

        Parameters
        ----------
        source_dir : str | Path
            存放原始视频的文件夹路径。
        save_dir : str | Path
            项目保存的根目录（生成的 _labels 文件夹会放在这里）。
        class_names : list
            预期的类别列表。
        extract_num : int
            回溯截取帧数。
        interval : int
            截取间隔。
        mode : {'full', 'mark_only'}, optional
            'full': 记录 CSV 并保存图片。
            'mark_only': 仅记录 CSV。
        """

        self.mode = mode

        # 1. 路径标准化
        self.source_dir = Path(source_dir)
        self.root_save_dir = Path(save_dir)

        if not self.source_dir.exists():
            raise FileNotFoundError(f"源文件夹不存在: {self.source_dir}")

        # 2. 生成项目输出目录: 源文件夹名 + "_labels"
        # 例如: 输入 "D:/Videos/Traffic"，输出 "D:/Datasets/Traffic_labels"
        self.project_dir = self.root_save_dir / f"{self.source_dir.name}_labels"
        self.project_dir.mkdir(parents=True, exist_ok=True)

        # 3. 配置文件路径
        self.config_path = self.project_dir / "project_config.csv"

        # 4. 配置处理核心逻辑 (Requirement #2)
        # 尝试加载现有配置，如果存在则覆盖传入参数，否则保存新参数
        self.config = self._init_configuration(class_names, extract_num, interval)

    def _init_configuration(self, input_classes, input_extract, input_interval):
        """
        加载或创建配置文件。
        优先读取磁盘上的配置，以保证项目延续性。
        """
        # 准备当前的配置字典
        current_config = {
            'class_names': input_classes,
            'extract_num': input_extract,
            'interval': input_interval
        }

        if self.config_path.exists():
            print(f"⚠️  检测到已有项目配置: {self.config_path}")
            print(">>  将忽略代码传入的参数，强制使用文件中的配置，以保持标注一致性。")

            try:
                loaded_config = {}
                with open(self.config_path, mode='r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if len(row) < 2: continue
                        key, val_str = row[0], row[1]

                        # 解析数据类型
                        if key == 'class_names':
                            # 使用 ast.literal_eval 安全地将字符串 "['a', 'b']" 转回 list
                            loaded_config[key] = ast.literal_eval(val_str)
                        elif key in ['extract_num', 'interval']:
                            loaded_config[key] = int(val_str)

                print(f"    -> 已加载配置: {loaded_config}")
                return loaded_config

            except Exception as e:
                print(f"❌ 读取配置文件失败: {e}。将使用新参数覆盖。")

        # 如果文件不存在，或读取失败，则写入新配置
        self._save_config(current_config)
        return current_config

    def _save_config(self, config_dict):
        """将配置写入 CSV"""
        try:
            with open(self.config_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['parameter', 'value', 'description'])  # Header

                writer.writerow(['class_names', str(config_dict['class_names']), 'Label categories'])
                writer.writerow(['extract_num', config_dict['extract_num'], 'Frames to look back'])
                writer.writerow(['interval', config_dict['interval'], 'Frame interval'])

            print(f"✅ 新项目配置已创建: {self.config_path}")
        except Exception as e:
            print(f"❌ 无法保存配置文件: {e}")

    def run(self):
        """
        执行批量处理。
        遍历源文件夹，依次启动 LabelingApp。
        """
        # 扫描所有视频文件 (不递归，只看当前层，如果需要递归可以用 rglob)
        video_files = [
            p for p in self.source_dir.iterdir()
            if p.suffix.lower() in self.VIDEO_EXTENSIONS
        ]

        # 排序，保证处理顺序一致
        video_files.sort()

        total = len(video_files)
        print(f"\n=== 开始批量处理: {total} 个视频 ===")
        print(f"源目录: {self.source_dir}")
        print(f"输出至: {self.project_dir}\n")

        for i, video_path in enumerate(video_files):
            print(f"------------------------------------------------")
            print(f"[{i + 1}/{total}] 正在处理: {video_path.name}")
            print(f"------------------------------------------------")

            # --- 核心调用 ---
            # 实例化你的 LabelingApp
            # 注意：save_dir 传入我们的 project_dir，LabelingApp 内部会在里面再创建 视频名 文件夹
            app = LabelingApp(
                video_path=video_path,
                save_dir=self.project_dir,
                class_names=self.config['class_names'],  # 使用（可能被覆盖的）配置
                extract_num=self.config['extract_num'],
                interval=self.config['interval'],
                mode=self.mode,
            )

            app.run()

            # 可选：这里可以加个询问逻辑，比如 "继续下一个吗？"
            # 或者自动全部跑完
            print(f"√ 视频 {video_path.name} 处理完毕 (或被跳过/退出)。")
            time.sleep(1)  # 稍微停顿，体验更好

        print("\n=== 所有视频处理完成 ===")

    def rebuild_batch(self,
                      new_extract_num: int,
                      new_interval: int,
                      target_root_dir: Union[str, Path] = './dataset',
                      copy_csv: bool = True):
        """
        批量重构数据集。
        读取当前项目的所有标记，使用新的截取参数（帧数/间隔），将图片重新生成到新的位置。

        Parameters
        ----------
        target_root_dir : str | Path
            新数据集存放的根目录。
            程序会自动在此目录下创建名为 "{SourceDir}_rebuilt" 的文件夹作为本项目的新根目录。
        new_extract_num : int
            新的向前回溯截取数量。
        new_interval : int
            新的截取间隔帧数。
        copy_csv : bool, default True
            是否将原始 CSV 标签文件也复制到新目录。
        """
        target_root = Path(target_root_dir)

        # 1. 构建新的项目目录 (e.g. "D:/Datasets/Traffic_rebuilt")
        # 区别于原来的 "_labeled"，这里用 "_rebuilt" 或自定义后缀
        new_project_dir = target_root / f"{self.source_dir.name}_rebuilt_extractNum_{new_extract_num}_interval_{new_interval}"
        new_project_dir.mkdir(parents=True, exist_ok=True)

        # 2. 扫描视频文件
        video_files = [
            p for p in self.source_dir.iterdir()
            if p.suffix.lower() in self.VIDEO_EXTENSIONS
        ]
        video_files.sort()

        total = len(video_files)

        print(f"\n========================================")
        print(f" ♻️ 开始批量重构 (Batch Rebuild)")
        print(f"========================================")
        print(f" 源项目配置: {self.project_dir}")
        print(f" 新输出目录: {new_project_dir}")
        print(f" 新参数设置: extract={new_extract_num}, interval={new_interval}")
        print(f" 待处理视频: {total} 个")
        print(f"========================================\n")

        # 3. 另外保存一份新的配置文件到新目录，方便未来追溯
        # 这里的 config 是新参数
        self._save_rebuild_config(new_project_dir, new_extract_num, new_interval)

        for i, video_path in enumerate(video_files):
            print(f"正在处理 [{i + 1}/{total}]: {video_path.name} ...")

            # --- 关键逻辑 ---
            # 1. 实例化 App 时，save_dir 必须指向【旧的】self.project_dir
            #    因为我们需要 App 自动去加载旧目录下的 CSV 标记数据
            app = LabelingApp(
                video_path=video_path,
                save_dir=self.project_dir,  # <--- 指向旧目录读取数据
                class_names=self.config['class_names']  # 保持类别映射一致
            )

            # 2. 调用重构方法，将结果输出到【新的】new_project_dir
            #    LabelingApp 内部会在 new_project_dir 下创建视频名文件夹
            app.rebuild_dataset(
                new_save_dir=new_project_dir,
                new_extract_num=new_extract_num,
                new_interval=new_interval,
                copy_csv=copy_csv
            )

            # 释放资源
            app.cleanup()
            print(f"√ 完成\n")

        print(f"=== ✅ 批量重构全部完成 ===")
        print(f"新数据集位于: {new_project_dir}")

    def _save_rebuild_config(self, save_path, ext_num, interval):
        """辅助方法：在新生成的文件夹里也存一份配置说明"""
        cfg_path = save_path / "rebuild_config.csv"
        try:
            with open(cfg_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['parameter', 'value', 'source_project'])
                writer.writerow(['class_names', str(self.config['class_names']), 'Inherited from source'])
                writer.writerow(['extract_num', ext_num, 'New setting'])
                writer.writerow(['interval', interval, 'New setting'])
                writer.writerow(['source_path', str(self.project_dir), 'Original Data Source'])
        except Exception:
            pass

    def consolidate_dataset(self, search_root: Union[str, Path] = None):
        """
        交互式整合数据集。
        1. 选择源项目文件夹。
        2. 扫描该项目中包含的所有类别。
        3. 用户选择需要导出的类别。
        4. 执行合并与统计。

        Parameters
        ----------
        search_root : str | Path, optional
            在哪里搜索文件夹。默认为初始化时的 save_dir。
        """
        root = Path(search_root) if search_root else self.root_save_dir
        base_name = self.source_dir.name

        # 1. 扫描符合条件的文件夹
        # 条件：以源文件夹名开头，且不是我们要生成的 SumUp 文件夹
        candidates = []
        for p in root.iterdir():
            if p.is_dir() and p.name.startswith(base_name) and "(SumUp)" not in p.name:
                candidates.append(p)

        candidates.sort()  # 排序，方便选择

        if not candidates:
            print(f"❌ 在 {root} 下未找到以 '{base_name}' 开头的项目文件夹。")
            return

        # 2. 终端交互：让用户选择
        print(f"\n=== 数据集整合 (Consolidation) ===")
        print(f"搜索根目录: {root}")
        print(f"发现以下可选项目:")
        for i, p in enumerate(candidates):
            print(f"  [{i + 1}] {p.name}")

        selected_idx = -1
        while True:
            try:
                choice = input(f"\n请选择要整合的文件夹序号 (1-{len(candidates)}): ")
                idx = int(choice) - 1
                if 0 <= idx < len(candidates):
                    selected_idx = idx
                    break
                else:
                    print("❌ 序号超出范围，请重试。")
            except ValueError:
                print("❌ 请输入数字。")

        src_folder = candidates[selected_idx]

        # --- 步骤 3: 【新增】扫描并选择类别 ---
        print(f"\n正在扫描 {src_folder.name} 中的类别...")

        # 扫描逻辑：遍历 src_folder -> 视频子文件夹 -> 类别子文件夹
        # 使用 set 去重
        available_classes = set()
        for video_dir in src_folder.iterdir():
            if video_dir.is_dir():
                for class_dir in video_dir.iterdir():
                    if class_dir.is_dir():
                        # 排除可能的非类别文件夹（虽然通常不会有）
                        available_classes.add(class_dir.name)

        if not available_classes:
            print("❌ 未在项目中找到任何类别文件夹。")
            return

        sorted_classes = sorted(list(available_classes))

        print(f"发现 {len(sorted_classes)} 种类别:")
        for i, cls_name in enumerate(sorted_classes):
            print(f"  [{i + 1}] {cls_name}")

        target_classes = set()
        while True:
            print("\n请输入要整合的类别序号 (用空格或逗号分隔，例如: 1, 3, 5)")
            print("直接回车(Enter)则默认选择【所有类别】")
            sel_str = input("您的选择: ").strip()

            if not sel_str:
                target_classes = set(sorted_classes)
                print(">> 已选择所有类别。")
                break

            try:
                # 兼容中文逗号，替换为英文逗号，再替换空格，最后分割
                cleaned_str = sel_str.replace('，', ',').replace(',', ' ')
                indices = [int(x) for x in cleaned_str.split()]

                valid_selection = True
                temp_set = set()
                for idx in indices:
                    real_idx = idx - 1
                    if 0 <= real_idx < len(sorted_classes):
                        temp_set.add(sorted_classes[real_idx])
                    else:
                        print(f"❌ 序号 {idx} 无效。")
                        valid_selection = False

                if valid_selection and temp_set:
                    target_classes = temp_set
                    print(f">> 已选择: {', '.join(target_classes)}")
                    break
                elif not temp_set:
                    print("❌ 未选择有效类别。")
            except ValueError:
                print("❌ 输入格式错误，请输入数字。")

        # 4. 准备目标文件夹
        # 命名规则: 原文件夹名 + (SumUp)
        dest_folder = root / f"{src_folder.name}(SumUp)"

        if dest_folder.exists():
            print(f"⚠️ 目标文件夹已存在: {dest_folder}")
            confirm = input("是否覆盖/合并? (y/n): ")
            if confirm.lower() != 'y':
                print("已取消操作。")
                return

        dest_folder.mkdir(parents=True, exist_ok=True)
        print(f"\n🚀 开始整合: {src_folder.name} -> {dest_folder.name}")

        # 5. 遍历与复制 (Flatten Logic)
        # 我们使用 rglob 递归查找所有 .jpg 图片
        # 目前的结构通常是: Project/VideoName/ClassX/img.jpg
        # 我们需要识别出 ClassX，这通常是图片父文件夹的名字

        stats = defaultdict(int)  # 用于统计 {class_name: count}
        total_copied = 0

        # 获取所有图片文件
        image_files = list(src_folder.rglob("*.jpg"))

        # 进度条估算
        total_files_scan = len(image_files)
        print(f"扫描到 {total_files_scan} 张图片，开始筛选复制...")

        for img_path in image_files:
            # 获取类别名 (父文件夹名)
            class_name = img_path.parent.name

            # 【关键修改】只处理用户选中的类别
            if class_name not in target_classes:
                continue

            # 如果父文件夹就是项目根目录(意外情况)，则跳过或设为 unknown
            if img_path.parent == src_folder:
                continue

            # 目标路径: dest_folder / class_name / img.jpg
            target_class_dir = dest_folder / class_name
            target_class_dir.mkdir(exist_ok=True)

            # 复制文件
            # 我们的文件名已经是 VideoName_Class_Frame.jpg，基本唯一，直接复制即可
            target_file = target_class_dir / img_path.name

            shutil.copy2(img_path, target_file)

            stats[class_name] += 1
            total_copied += 1

            if total_copied % 50 == 0:
                print(f"  已复制 {total_copied} 张...", end='\r')

        print(f"  已复制 {total_copied} 张... 完成！      ") # 空格是为了覆盖之前的\r输出

        # 6. 生成统计报表
        self._save_statistics(dest_folder, src_folder, stats, total_copied)

    def _save_statistics(self, save_path, src_name, stats, total):
        """生成详细的统计 CSV"""
        csv_path = save_path / "dataset_stats.csv"
        try:
            with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Attribute', 'Value'])
                writer.writerow(['Source Folder', src_name])
                writer.writerow(['Total Images', total])
                writer.writerow([])  # 空行
                writer.writerow(['Class Name', 'Count', 'Percentage'])

                # 按数量降序排列
                sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)

                for cls, count in sorted_stats:
                    percent = (count / total * 100) if total > 0 else 0
                    writer.writerow([cls, count, f"{percent:.2f}%"])

            print(f"\n✅ 整合完成！")
            print(f"统计文件已保存: {csv_path}")
            print("各类别统计:")
            for cls, count in sorted_stats:
                print(f"  - {cls}: {count}")

        except Exception as e:
            print(f"❌ 保存统计信息失败: {e}")