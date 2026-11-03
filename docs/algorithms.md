# 算法说明

## 1. 人脸情绪识别：YuNet + FER+ + 几何校准

### 1.1 检测

- 模型：`backend/data/face_detection_yunet_2023mar.onnx`（YuNet，约 232 KB）。
- 输入图片限制长边 1280，减少 CPU 推理时间。
- 输出人脸框、检测分数和 5 个关键点：右眼、左眼、鼻尖、右嘴角、左嘴角。
- 检测分数低于 0.65 的结果丢弃，取面积最大人脸为主结果，最多分析 5 张脸。
- 没有检测到人脸返回 422，`data.reason = "NO_FACE"`，前端呈现可读错误态。

### 1.2 FER+ CNN

模型：`backend/data/emotion-ferplus-8.onnx`（FER+，约 33.4 MB）。

将人脸裁切并灰度化到 64×64 后输入，得到 8 类概率：

```
neutral, happiness, surprise, sadness, anger, disgust, fear, contempt
```

映射到产品使用的 6 类：

- `disgust` → 70% angry + 30% neutral
- `contempt` → 50% neutral + 50% sad
- 重新归一化

### 1.3 几何先验

- **嘴部**：由嘴角关键点定位 ROI，Otsu 阈值提取暗区，逐列取最上缘并做二次曲线拟合；曲线曲率作为笑容/下垂线索，暗区比例作为张口程度。
- **眼睛**：眼中心小块的灰度对比度；睁眼通常有更高的虹膜/巩膜对比，闭眼/眯眼对比下降。
- **眉间**：上脸左右与中部亮度差，用作愤怒紧张度的弱先验。

融合：

```
confidence = max(cnn_scores)
blend = 0.90 if confidence >= 0.45 else 0.70
scores = normalize(blend * cnn + (1 - blend) * geometry)
```

### 1.4 边界

- 检测器与 CNN 的准确率受遮挡、极端侧脸、强逆光、口罩影响；
- 输出不是医学/心理诊断；
- 图片只在进程内处理，不保存、不上传第三方；数据库仅保存情绪标签、概率与耗时。

---

## 2. 曲调情绪识别：Krumhansl + Thayer

### 2.1 音频特征

对本地 WAV 读取单声道 PCM，帧长 2048、hop 512：

| 特征 | 方法 |
|---|---|
| BPM | 短时能量正差分形成 onset envelope，55–180 BPM 范围做自相关峰值搜索；高能量下修正半拍 |
| 能量 | 帧 RMS 归一化 |
| 谱质心 | FFT 幅度加权平均频率 |
| 调式 | 频谱折回 12 维 chroma，Krumhansl major/minor 模板旋转相关 |
| 过零率 | 短时符号变化均值 |
| 动态范围 | 90 分位 / 20 分位 RMS |

### 2.2 Thayer 二维映射

```
tempo_norm     = clip((BPM - 50) / 130)
brightness_norm= clip((centroid - 450) / 2500)
energy_norm    = clip(RMS / 0.18)

arousal = 0.04 + 0.42*tempo_norm + 0.48*energy_norm + 0.06*brightness_norm
valence = mode_base + 0.10*(1-zcr_norm) + 0.08*brightness_norm - dynamic_penalty
```

六类参考坐标：

| emotion | valence | arousal |
|---|---:|---:|
| happy | 0.85 | 0.65 |
| sad | 0.20 | 0.35 |
| angry | 0.20 | 0.80 |
| fear | 0.30 | 0.55 |
| surprised | 0.65 | 0.80 |
| neutral | 0.55 | 0.45 |

最近邻映射得到曲目情绪初判。本地曲库使用人工试听标签作为先验：

```
mood_scores = normalize(0.55 * audio_scores + 0.45 * curated_one_hot)
```

原始算法判定保留在 `audio_features.analyzedMood`。

### 2.3 在线歌曲

iTunes Search API 返回官方 30 秒预览与曲风元数据，无法在服务端下载音频，因此在线结果只做元数据匹配，UI 标注 `ITUNES · 30S`。本地曲目始终优先。

---

## 3. 推荐：加权混合 + MMR

```
score = 0.42 × P(current_emotion)
      + 0.28 × (1 - distance(track_valence_arousal, emotion_target) / √2)
      + 0.12 × taste_similarity
      + 0.10 × novelty
      + 0.08 × normalized_popularity
```

- 用户品味向量来自收藏和喜欢/不喜欢反馈；明确不喜欢的曲目直接排除。
- 先过滤同频曲目（情绪概率 ≥ 0.12 或人工标签匹配）；不足 4 首时用最接近的曲目补位。
- MMR 简化实现：同一艺人最多 2 首，逐步填满列表。
- 每张卡片返回 `reason`（BPM、调式、能量和情绪目标）。

### 为什么不是深度学习推荐

单机、免费、可解释优先。当前数据规模为演示曲库，透明加权比不可解释的向量召回更容易验收和调试；接口已把 `score`、`affinity`、`moodProbability`、`reason` 暴露出来，可独立验证。
