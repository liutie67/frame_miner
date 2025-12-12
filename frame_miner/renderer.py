import cv2
import numpy as np
from .config import AppConfig


class UIRenderer:
    """
    负责将UI元素绘制到视频帧上。
    未来可在此扩展 PIL 绘制以支持中文字体。
    """

    def __init__(self, key_map, class_names):
        """
        Parameters
        ----------
        key_map : dict
            按键码到标签的映射。
        class_names : list
            类别名称列表。
        """
        self.key_map = key_map
        self.class_names = class_names
        self.cfg = AppConfig

    def get_central_pos(self, msg, target_width, target_height, direction='w'):
        # 计算文字大小以居中
        (w_title, h_title), _ = cv2.getTextSize(msg, self.cfg.FONT, 1.8, 3)
        (w_sub, h_sub), _ = cv2.getTextSize(msg, self.cfg.FONT, 1.0, 2)

        x_title = (target_width - w_title) // 2
        x_sub = (target_width - w_sub) // 2
        y_center = target_height // 2

    def draw_shadow_text(self, img, text, pos, scale, color, thickness, offset=2):
        """绘制带阴影的文字，增加对比度。"""
        x, y = pos
        # Shadow
        cv2.putText(img, text, (x + offset, y + offset),
                    self.cfg.FONT, scale, self.cfg.COLORS['shadow'], thickness)
        # Body
        cv2.putText(img, text, (x, y),
                    self.cfg.FONT, scale, color, thickness)

    def draw_interface(self, frame, current_state):
        """
        绘制主界面所有元素（不修改原图，返回复本）。

        Parameters
        ----------
        frame : np.ndarray
            原始视频帧。
        current_state : dict
            包含当前UI所需的所有状态数据 (frame_idx, fps, markers, message, etc.)

        Returns
        -------
        np.ndarray
            绘制了UI的图像。
        """
        display_img = frame.copy()
        h, w = display_img.shape[:2]

        start_y = 80
        # 1. Info Text
        info = f"Frame: {current_state['curr_pos']}/{current_state['total_frames']} | Speed: x{current_state['speed']}"
        info_help = " [1][2][3][5]"
        info = info + info_help
        self.draw_shadow_text(display_img, info, (20, 40), 1, (174, 20, 255), 2)

        # 2. Status
        status = "[SPACE] PAUSED" if current_state['paused'] else "[SPACE] PLAYING"
        s_color = self.cfg.COLORS['red'] if current_state['paused'] else self.cfg.COLORS['green']
        self.draw_shadow_text(display_img, status, (w - 300, 40), 1, s_color, 2)
        if current_state['paused']:
            status_help_line1 = "[D] Previous frame"
            self.draw_shadow_text(display_img, status_help_line1, (w - 330, 100), 1, s_color, 1)
            status_help_line2 = "[F] Next frame"
            self.draw_shadow_text(display_img, status_help_line2, (w - 330, 100 + 45), 1, s_color, 1)

        # 3. Menu List (Vertical)
        for i, (k_code, label) in enumerate(self.key_map.items()):
            # Find short code for color (e.g., 'z')
            short_code = self.cfg.BASE_CHARS[i] if i < len(self.cfg.BASE_CHARS) else 'default'
            color = self.cfg.CLASS_COLORS.get(short_code, self.cfg.COLORS['white'])

            text = f"[{short_code.upper()}] {label}"
            self.draw_shadow_text(display_img, text, (20, start_y + i * 30), 0.7, color, 1, offset=1)

        # 4. Center Marker Notification (Ghost Marker)
        if current_state['is_marked']:
            m_label = current_state['marker_label']

            if m_label in self.key_map.values():
                key = next((k for k, v in self.key_map.items() if v == m_label), None)
                m_color = self.cfg.CLASS_COLORS.get(chr(key), self.cfg.COLORS['white'])
            else:
                m_color = self.cfg.CLASS_COLORS.get(m_label, self.cfg.COLORS['white'])

            fontScale = 5
            fontThickness = 10
            if len(m_label) == 1:
                if ord(m_label) in self.key_map.keys():
                    center_text = f"[{self.key_map[ord(m_label)]}]"
            else:
                center_text = f"[{m_label}]"
            text_size = cv2.getTextSize(center_text, self.cfg.FONT, fontScale, fontThickness)[0]
            cx, cy = (w - text_size[0]) // 2, h // 2

            # Semi-transparent bg
            # overlay = display_img.copy()
            # cv2.rectangle(overlay, (cx - 10, cy - 40), (cx + text_size[0] + 10, cy + 10), (0, 0, 0), -1)
            # cv2.addWeighted(overlay, 0.5, display_img, 0.5, 0, display_img)

            self.draw_shadow_text(display_img, center_text, (cx, cy), fontScale, m_color, fontThickness)

        # 5. Global Message (Toast)
        msg = current_state.get('ui_message')
        if msg:
            font = cv2.FONT_HERSHEY_SIMPLEX
            fontscale = 1.8
            thickness = 2
            h, w = display_img.shape[:2]
            (w_msg, h_msg), _ = cv2.getTextSize(msg, font, fontscale, thickness)
            self.draw_shadow_text(display_img, msg, ((w-w_msg)//2, start_y + h_msg//2), fontscale,
                                  self.cfg.COLORS['white'], thickness, offset=1)

        # 6. Progress Bar
        self._draw_progress_bar(display_img, current_state['curr_pos'],
                                current_state['total_frames'], current_state['markers'])

        return display_img

    def _draw_progress_bar(self, img, curr, total, markers):
        h, w = img.shape[:2]
        bar_h = 20
        bar_y = h - 30

        # Background
        cv2.rectangle(img, (0, bar_y), (w, bar_y + bar_h), self.cfg.COLORS['gray'], -1)
        status_help_line3 = "[BACKSPACE] Withdraw]"
        self.draw_shadow_text(img, status_help_line3, (w - 400, bar_y - bar_h), 1, self.cfg.COLORS['light_gray'], 2)

        if total > 0:
            # Progress
            pw = int((curr / total) * w)
            cv2.rectangle(img, (0, bar_y), (pw, bar_y + bar_h), self.cfg.COLORS['light_gray'], -1)

            # Markers
            for f_id, label_code in markers.items():
                mx = int((f_id / total) * w)
                if label_code in self.key_map.values():
                    key = next((k for k, v in self.key_map.items() if v == label_code), None)
                    c = self.cfg.CLASS_COLORS.get(chr(key), self.cfg.COLORS['white'])
                    cv2.line(img, (mx, bar_y), (mx, bar_y + bar_h), c, 1)
                else:
                    c = self.cfg.CLASS_COLORS.get(label_code, self.cfg.COLORS['white'])
                    cv2.line(img, (mx, bar_y), (mx, bar_y + bar_h), c, 2)
