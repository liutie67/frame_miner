import cv2


class VideoController:
    """
    视频流控制包装器。
    """

    def __init__(self, path):
        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            raise IOError(f"Cannot open video: {path}")

        self.name = path.stem
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self.current_frame_idx = 0
        self.frame_cache = None

    def read(self):
        """读取下一帧"""
        ret, frame = self.cap.read()
        if ret:
            self.current_frame_idx = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
            self.frame_cache = frame
        return ret, frame

    def seek(self, frame_idx):
        """跳转到指定帧"""
        target = max(0, min(frame_idx, self.total_frames - 1))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, target)
        self.read()  # Read to update cache

    def get_ms(self):
        """获取当前毫秒数"""
        return (self.current_frame_idx / self.fps) * 1000.0 if self.fps > 0 else 0

    def release(self):
        self.cap.release()