import cv2
import numpy as np

class SmartCropper:
    def __init__(self, target_ratio=(9, 16), smoothing_factor=0.1):
        """
        No-AI algorithmic crop-tracker.
        - smoothing_factor (0-1): EMA factor for jitter-free panning (lower = smoother/slower).
        """
        data_dir = cv2.data.haarcascades
        self.face_cascade = cv2.CascadeClassifier(data_dir + 'haarcascade_frontalface_default.xml')
        self.profile_cascade = cv2.CascadeClassifier(data_dir + 'haarcascade_profileface.xml')

        self.target_ratio = target_ratio
        self.smoothing = smoothing_factor
        self.ema_x = None
        self.prev_gray = None
        self.prev_pts = None

    def _get_face_centers(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = list(self.face_cascade.detectMultiScale(gray, 1.1, 4))
        profiles = list(self.profile_cascade.detectMultiScale(gray, 1.1, 4))

        centers = []
        for (x, y, w, h) in faces + profiles:
            centers.append((x + w//2, y + h//2))
        return centers

    def _get_flow_center(self, frame, frame_size):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.prev_gray is None:
            self.prev_gray = gray
            return frame_size[0] // 2

        flow = cv2.calcOpticalFlowFarneback(self.prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        motion_x = np.mean(flow[..., 0])

        self.prev_gray = gray
        return int(frame_size[0] // 2 + motion_x * 10)

    def get_crop_coords(self, frame):
        h, w = frame.shape[:2]
        target_w = int(h * self.target_ratio[0] / self.target_ratio[1])

        face_centers = self._get_face_centers(frame)

        # Logic: Two faces far apart -> split screen
        if len(face_centers) >= 2:
            xs = sorted([c[0] for c in face_centers])
            if xs[-1] - xs[0] > w * 0.3:
                # Return split layout coordinates
                return {"type": "split", "h": h // 2}

        # Single focus tracking
        if face_centers:
            center_x = int(np.mean([c[0] for c in face_centers]))
        else:
            center_x = self._get_flow_center(frame, (w, h))

        # Apply 1D EMA smoothing (Kalman-like)
        if self.ema_x is None:
            self.ema_x = center_x
        else:
            self.ema_x = self.ema_x * (1 - self.smoothing) + center_x * self.smoothing

        crop_x = int(np.clip(self.ema_x - target_w // 2, 0, w - target_w))
        return {"type": "single", "x": crop_x, "w": target_w}
