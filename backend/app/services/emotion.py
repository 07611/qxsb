"""本地人脸情绪识别。

算法组合（全部在服务器本地执行，图片不上传到第三方）：
1. OpenCV YuNet（轻量 CNN）检测人脸并输出 5 个关键点；
2. FER+ 8 类表情 ONNX 卷积网络对 64×64 灰度人脸块做前向推理；
3. 由关键点定位双眼与嘴角，结合嘴线抛物线、眼周对比度、眉间明暗构成
   可解释几何先验，在 CNN 置信度不足时做轻量校准；
4. 将 FER+ 的 8 类结果映射为产品使用的 6 类，并输出完整概率分布。

这是经典的「轻量 CNN 检测 + 小型 CNN 表情分类 + 几何校准」组合，单张图片
CPU 推理通常在几十到一百毫秒。OpenCV 5 不再附带 Haar cascade，因此使用
YuNet（232KB）替代 Haar，并随项目离线分发。
"""

from __future__ import annotations

import io
import json
import logging
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps

from ..config import settings
from ..errors import APIError

logger = logging.getLogger("moodwave.emotion")

EMOTIONS = ["happy", "sad", "angry", "surprised", "fear", "neutral"]
EMOTION_LABELS = {
    "happy": "愉悦",
    "sad": "低落",
    "angry": "愤怒",
    "surprised": "惊喜",
    "fear": "不安",
    "neutral": "平静",
}
EMOTION_COLORS = {
    "happy": "#E8A23B",
    "sad": "#5B7DB1",
    "angry": "#E8552F",
    "surprised": "#9B6BD6",
    "fear": "#4F8C86",
    "neutral": "#6B6B72",
}
# FER+ 官方 8 类顺序
FER_LABELS = ["neutral", "happy", "surprised", "sad", "angry", "disgust", "fear", "contempt"]


class EmotionEngine:
    def __init__(self) -> None:
        self.net = None
        self.face_detector = None
        self.face_model_error: str | None = None
        self.model_loaded_at: float | None = None
        self.model_error: str | None = None
        from ..config import BACKEND_DIR

        face_model = BACKEND_DIR / "data" / "face_detection_yunet_2023mar.onnx"
        if face_model.exists():
            try:
                self.face_detector = cv2.FaceDetectorYN.create(
                    _ascii_model_path(face_model), "", (320, 320), score_threshold=0.65, nms_threshold=0.3, top_k=5000
                )
                logger.info("face_detector_loaded path=%s", face_model)
            except Exception as exc:
                self.face_model_error = f"YuNet 人脸检测器加载失败：{exc}"
                logger.warning(self.face_model_error)
        else:
            self.face_model_error = "YuNet 人脸检测模型缺失"
            logger.warning(self.face_model_error)
        self._try_load_model()

    def _try_load_model(self) -> None:
        path = Path(settings.model_path)
        if not path.exists() or path.stat().st_size < 1_000_000:
            self.model_error = "ONNX 模型未安装，使用几何先验引擎"
            logger.warning(self.model_error)
            return
        try:
            self.net = cv2.dnn.readNetFromONNX(_ascii_model_path(path))
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.model_loaded_at = time.time()
            logger.info("emotion_model_loaded path=%s bytes=%s", path, path.stat().st_size)
        except Exception as exc:
            self.model_error = f"ONNX 模型加载失败：{exc}"
            self.net = None
            logger.warning(self.model_error)

    @property
    def engine_name(self) -> str:
        if self.net is not None:
            return "YuNet 关键点 + FER+ CNN + 几何校准"
        return "YuNet 关键点 + 几何先验"

    def status(self) -> dict:
        return {
            "engine": self.engine_name,
            "cnnAvailable": self.net is not None,
            "faceDetectorAvailable": self.face_detector is not None,
            "modelError": self.model_error or self.face_model_error,
        }

    # ── 图片解码 ─────────────────────────────────────────────────────
    @staticmethod
    def load_image(raw: bytes) -> np.ndarray:
        if len(raw) > settings.max_image_mb * 1024 * 1024:
            raise APIError(413, f"图片不能超过 {settings.max_image_mb}MB")
        try:
            pil = Image.open(io.BytesIO(raw))
            pil = ImageOps.exif_transpose(pil).convert("RGB")
        except Exception as exc:
            raise APIError(422, "无法解析图片，请上传 JPG / PNG / WebP") from exc
        # 长边限制，兼顾速度与小人脸可检出率
        max_side = 1280
        if max(pil.size) > max_side:
            ratio = max_side / max(pil.size)
            pil = pil.resize((max(1, int(pil.width * ratio)), max(1, int(pil.height * ratio))), Image.Resampling.LANCZOS)
        return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

    def detect_faces(self, image: np.ndarray) -> list[dict[str, Any]]:
        if self.face_detector is None:
            raise APIError(503, "人脸检测模型不可用，请检查 YuNet 模型文件")
        height, width = image.shape[:2]
        self.face_detector.setInputSize((width, height))
        _retval, raw_faces = self.face_detector.detect(image)
        if raw_faces is None:
            return []
        faces: list[dict[str, Any]] = []
        for item in raw_faces:
            x, y, w, h = [int(max(0, value)) for value in item[:4]]
            score = float(item[-1])
            landmarks = item[4:14].reshape(5, 2).astype(float)
            if w <= 0 or h <= 0:
                continue
            faces.append({"x": min(x, width - 1), "y": min(y, height - 1), "w": min(w, width - x), "h": min(h, height - y), "score": score, "landmarks": landmarks})
        faces.sort(key=lambda face: face["w"] * face["h"], reverse=True)
        return faces[:5]

    # ── CNN 推理 ─────────────────────────────────────────────────────
    def _cnn_scores(self, face_bgr: np.ndarray) -> dict[str, float] | None:
        if self.net is None:
            return None
        try:
            gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA)
            # FER+ ONNX 接收 1×1×64×64 的 float32 灰度图，模型内置输入缩放。
            blob = gray.astype(np.float32).reshape(1, 1, 64, 64)
            self.net.setInput(blob)
            raw = self.net.forward()
            vector = np.asarray(raw).reshape(-1)[:8].astype(np.float64)
            if np.any(~np.isfinite(vector)):
                return None
            if vector.min() < 0 or abs(float(vector.sum()) - 1.0) > 0.05:
                vector = np.exp(vector - vector.max())
                vector /= vector.sum()
            labels = FER_LABELS
            mapped = {emotion: 0.0 for emotion in EMOTIONS}
            for label, probability in zip(labels, vector):
                if label in mapped:
                    mapped[label] += float(probability)
                elif label == "disgust":
                    mapped["angry"] += float(probability) * 0.7
                    mapped["neutral"] += float(probability) * 0.3
                elif label == "contempt":
                    mapped["neutral"] += float(probability) * 0.5
                    mapped["sad"] += float(probability) * 0.5
            return _normalize(mapped)
        except Exception as exc:
            logger.warning("emotion_cnn_inference_failed error=%s", exc)
            return None

    # ── 几何先验 ─────────────────────────────────────────────────────
    def _geometry_scores(
        self, face_bgr: np.ndarray, landmarks: list[tuple[float, float]] | None = None
    ) -> tuple[dict[str, float], dict[str, float]]:
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        gray_eq = cv2.equalizeHist(gray)
        eye_open = 0.5
        eye_contrast = 0.0
        if landmarks and len(landmarks) >= 5:
            eye_centers = landmarks[:2]
            contrasts = []
            for cx, cy in eye_centers:
                ex, ey = int(cx * w), int(cy * h)
                half_w, half_h = max(8, int(w * 0.13)), max(6, int(h * 0.09))
                patch = gray[max(0, ey - half_h) : min(h, ey + half_h), max(0, ex - half_w) : min(w, ex + half_w)]
                if patch.size:
                    contrasts.append(float(np.std(patch)) / 42.0)
            if contrasts:
                eye_contrast = float(np.clip(np.mean(contrasts), 0, 1.6))
                eye_open = float(np.clip(0.22 + eye_contrast * 0.72, 0, 1.5))
            mouth_points = landmarks[3:5]
            mouth_center_x = float(np.mean([point[0] for point in mouth_points])) * w
            mouth_center_y = float(np.mean([point[1] for point in mouth_points])) * h
            mouth_w = max(16, int(float(np.abs(mouth_points[0][0] - mouth_points[1][0])) * w * 1.3))
            mouth_h = max(12, int(h * 0.24))
            x_start = max(0, int(mouth_center_x - mouth_w / 2))
            x_end = min(w, int(mouth_center_x + mouth_w / 2))
            y_start = max(0, int(mouth_center_y - mouth_h * 0.45))
            y_end = min(h, int(mouth_center_y + mouth_h))
            mouth_roi = gray[y_start:y_end, x_start:x_end]
        else:
            mouth_roi = gray[int(h * 0.58) : int(h * 0.98), int(w * 0.18) : int(w * 0.82)]
        if mouth_roi.size == 0:
            return _normalize({"neutral": 1}), {"eyeOpen": eye_open, "smile": 0, "mouthCurve": 0}
        blur = cv2.GaussianBlur(mouth_roi, (5, 5), 0)
        _, dark = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        dark_ratio = float(np.count_nonzero(dark)) / dark.size
        xs: list[int] = []
        ys: list[int] = []
        mh, mw = dark.shape
        for col in range(mw):
            rows = np.flatnonzero(dark[:, col])
            if rows.size:
                xs.append(col)
                ys.append(int(rows[0]))
        curve = 0.0
        if len(xs) > mw * 0.25:
            try:
                a, _b, _c = np.polyfit(np.array(xs, dtype=float), np.array(ys, dtype=float), 2)
                curve = float(np.clip(-a * mw * mw / 100.0, -1.0, 1.0))
            except Exception:
                curve = 0.0
        mouth_open = float(np.clip(dark_ratio / 0.34, 0.0, 1.2))

        brow_band = gray_eq[int(h * 0.22) : int(h * 0.43), :]
        if brow_band.size:
            left = float(np.mean(brow_band[:, : w // 2]))
            right = float(np.mean(brow_band[:, w // 2 :]))
            inner_left = float(np.mean(brow_band[:, int(w * 0.28) : int(w * 0.44)]))
            inner_right = float(np.mean(brow_band[:, int(w * 0.56) : int(w * 0.72)]))
            brow_tension = float(np.clip(((left + right) / 2 - (inner_left + inner_right) / 2) / 48.0, 0, 1))
        else:
            brow_tension = 0.0

        scores = {emotion: 0.06 for emotion in EMOTIONS}
        scores["neutral"] = 0.22
        if curve > 0.025 or (mouth_open > 0.1 and eye_contrast > 0.9):
            scores["happy"] += 0.24 + 0.46 * max(curve, 0)
        if curve < -0.02 or (eye_open < 0.5 and mouth_open < 0.2):
            scores["sad"] += 0.14 + 0.35 * max(0, -curve) + 0.12 * max(0, 0.62 - eye_open)
        if brow_tension > 0.08:
            scores["angry"] += 0.10 + 0.62 * brow_tension
        if eye_open > 0.72 or mouth_open > 0.5:
            scores["surprised"] += 0.1 + 0.34 * max(0, eye_open - 0.55) + 0.3 * max(0, mouth_open - 0.38)
            if brow_tension > 0.12:
                scores["fear"] += 0.08 + 0.22 * max(0, eye_open - 0.65) + 0.18 * brow_tension
        if mouth_open < 0.14 and abs(curve) < 0.08 and brow_tension < 0.07:
            scores["neutral"] += 0.24
        return _normalize(scores), {
            "eyeOpen": round(eye_open, 3),
            "eyeContrast": round(eye_contrast, 3),
            "mouthCurve": round(curve, 3),
            "mouthOpen": round(mouth_open, 3),
            "browTension": round(brow_tension, 3),
        }

    def analyze_bytes(self, raw: bytes, source: str = "upload") -> dict:
        started = time.perf_counter()
        image = self.load_image(raw)
        faces = self.detect_faces(image)
        if not faces:
            raise APIError(
                422,
                "没有检测到清晰的人脸，请正对镜头、保证光线充足后重试",
                data={"reason": "NO_FACE"},
            )
        faces.sort(key=lambda face: face["w"] * face["h"], reverse=True)
        primary_results = []
        for face in faces:
            x, y, w, h = face["x"], face["y"], face["w"], face["h"]
            pad_x, pad_y = int(w * 0.08), int(h * 0.1)
            x0, y0 = max(0, x - pad_x), max(0, y - pad_y)
            x1, y1 = min(image.shape[1], x + w + pad_x), min(image.shape[0], y + h + pad_y)
            crop = image[y0:y1, x0:x1]
            crop_w, crop_h = max(1, x1 - x0), max(1, y1 - y0)
            landmark_norm = [
                (float((point[0] - x0) / crop_w), float((point[1] - y0) / crop_h))
                for point in face["landmarks"]
            ]
            cnn = self._cnn_scores(crop)
            geometry, features = self._geometry_scores(crop, landmark_norm)
            if cnn is not None:
                confidence = max(cnn.values())
                blend = 0.9 if confidence >= 0.45 else 0.7
                scores = {emotion: cnn[emotion] * blend + geometry[emotion] * (1 - blend) for emotion in EMOTIONS}
            else:
                scores = geometry
            scores = _normalize(scores)
            emotion = max(scores, key=scores.get)
            landmarks_public = [
                {
                    "x": round(float(point[0]) / image.shape[1], 5),
                    "y": round(float(point[1]) / image.shape[0], 5),
                }
                for point in face["landmarks"]
            ]
            primary_results.append(
                {
                    "emotion": emotion,
                    "label": EMOTION_LABELS[emotion],
                    "color": EMOTION_COLORS[emotion],
                    "confidence": round(scores[emotion], 4),
                    "scores": {k: round(v, 4) for k, v in scores.items()},
                    "box": {
                        "x": round(x / image.shape[1], 5),
                        "y": round(y / image.shape[0], 5),
                        "w": round(w / image.shape[1], 5),
                        "h": round(h / image.shape[0], 5),
                    },
                    "landmarks": landmarks_public,
                    "detectionScore": round(face["score"], 4),
                    "imageWidth": image.shape[1],
                    "imageHeight": image.shape[0],
                    "quality": {
                        "faceWidth": w,
                        "faceHeight": h,
                        "geometryFeatures": {k: round(v, 3) if isinstance(v, float) else v for k, v in features.items()},
                    },
                }
            )
        primary = primary_results[0]
        elapsed = int((time.perf_counter() - started) * 1000)
        return {
            **primary,
            "faceCount": len(faces),
            "allFaces": primary_results,
            "inferenceMs": elapsed,
            "engine": self.engine_name,
            "source": source,
            "algorithmVersion": "moodwave-yunet-ferplus-geometry-v2",
        }

    def analyze_path(self, path: Path, source: str = "demo") -> dict:
        if not path.exists():
            raise APIError(404, "演示图片不存在，请先执行种子脚本")
        return self.analyze_bytes(path.read_bytes(), source=source)


def _normalize(scores: dict[str, float]) -> dict[str, float]:
    values = {emotion: max(0.0, float(scores.get(emotion, 0.0))) for emotion in EMOTIONS}
    total = sum(values.values())
    if total <= 0:
        return {emotion: round(1 / len(EMOTIONS), 4) for emotion in EMOTIONS}
    return {emotion: value / total for emotion, value in values.items()}


def _ascii_model_path(path: Path) -> str:
    """OpenCV 在 Windows 上读取非 ASCII 路径会失败，复制到临时 ASCII 目录后加载。"""
    if str(path).isascii():
        return str(path)
    target_dir = Path(tempfile.gettempdir()) / "moodwave_models"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / path.name
    if not target.exists() or target.stat().st_size != path.stat().st_size:
        shutil.copy2(path, target)
    return str(target)


engine = EmotionEngine()


def demos() -> list[dict]:
    manifest = settings.demo_dir / "manifest.json"
    if not manifest.exists():
        return []
    try:
        items = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        return []
    result = []
    for item in items:
        file_path = settings.demo_dir / item["file"]
        if not file_path.exists():
            continue
        result.append(
            {
                **item,
                "url": f"/media/demo/{item['file']}",
                "available": True,
            }
        )
    return result
