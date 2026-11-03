"""音频特征与曲调情绪分析。

思路来自经典 MIR（Music Information Retrieval）特征：
- 能量包络自相关估计 BPM；
- FFT 谱质心衡量明亮度；
- 八度折叠的 chroma 与 Krumhansl 调性模板相关，判断大调/小调；
- 能量、谱通量、过零率估计唤醒度；
- 调式、BPM、谱质心共同映射 Thayer 二维情绪模型的 valence / arousal。
"""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

EMOTION_TARGETS = {
    "happy": {"valence": 0.85, "arousal": 0.65},
    "sad": {"valence": 0.20, "arousal": 0.35},
    "angry": {"valence": 0.20, "arousal": 0.80},
    "fear": {"valence": 0.30, "arousal": 0.55},
    "surprised": {"valence": 0.65, "arousal": 0.80},
    "neutral": {"valence": 0.55, "arousal": 0.45},
}

MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def _read_wave(path: Path, max_seconds: float = 120) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wav:
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        frames = min(wav.getnframes(), int(sample_rate * max_seconds))
        raw = wav.readframes(frames)
    if width == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128.0
    elif width == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError("unsupported sample width")
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data, sample_rate


def _chroma(spectrum: np.ndarray, freqs: np.ndarray) -> np.ndarray:
    chroma = np.zeros(12, dtype=np.float64)
    usable = (freqs > 55) & (freqs < 4000)
    for freq, magnitude in zip(freqs[usable], spectrum[usable]):
        if magnitude <= 0 or freq <= 0:
            continue
        midi = 69 + 12 * math.log2(freq / 440.0)
        pitch_class = int(round(midi)) % 12
        chroma[pitch_class] += float(magnitude)
    if chroma.sum() > 0:
        chroma /= chroma.sum()
    return chroma


def _krumhansl(chroma: np.ndarray) -> tuple[str, float]:
    best_mode = "major"
    best_corr = -1.0
    for mode, profile in (("major", MAJOR_PROFILE), ("minor", MINOR_PROFILE)):
        for shift in range(12):
            rotated = np.roll(profile, shift)
            corr = float(np.corrcoef(chroma, rotated)[0, 1]) if np.std(chroma) > 0 else 0.0
            if corr > best_corr:
                best_corr = corr
                best_mode = mode
    return best_mode, float(np.clip(best_corr, -1, 1))


def analyze_audio(path: Path) -> dict:
    samples, sample_rate = _read_wave(path)
    if samples.size < sample_rate * 2:
        raise ValueError("audio too short")
    frame = 2048
    hop = 512
    if samples.size < frame:
        samples = np.pad(samples, (0, frame - samples.size))
    frame_count = 1 + (samples.size - frame) // hop
    window = np.hanning(frame)
    energies = np.empty(frame_count)
    centroids = np.empty(frame_count)
    spectra_accum: list[np.ndarray] = []
    zero_crossings = 0.0
    for index in range(frame_count):
        chunk = samples[index * hop : index * hop + frame]
        windowed = chunk * window
        spectrum = np.abs(np.fft.rfft(windowed))
        freqs = np.fft.rfftfreq(frame, 1 / sample_rate)
        energy = float(np.sqrt(np.mean(chunk**2)))
        energies[index] = energy
        total = float(spectrum.sum()) + 1e-9
        centroids[index] = float((freqs * spectrum).sum() / total)
        zero_crossings += float(np.mean(np.abs(np.diff(np.signbit(chunk).astype(int)))))
        if index % 8 == 0:
            spectra_accum.append(spectrum)
    avg_spectrum = np.mean(spectra_accum, axis=0) if spectra_accum else np.zeros(frame // 2 + 1)
    freqs = np.fft.rfftfreq(frame, 1 / sample_rate)
    chroma = _chroma(avg_spectrum, freqs)
    mode, mode_corr = _krumhansl(chroma)

    # onset strength = 正向能量差分，自相关寻找 60-180 BPM 的周期
    onset = np.maximum(0, np.diff(energies))
    tempo = 90.0
    if onset.size > 16 and onset.std() > 1e-5:
        onset = onset - onset.mean()
        corr = np.correlate(onset, onset, mode="full")[onset.size - 1 :]
        min_lag = int(60 * sample_rate / hop / 180)
        max_lag = int(60 * sample_rate / hop / 55)
        high = min(max_lag, corr.size - 1)
        low = max(1, min_lag)
        if high > low:
            lag = low + int(np.argmax(corr[low:high]))
            if lag > 0:
                tempo = 60.0 * sample_rate / hop / lag
                while tempo < 60:
                    tempo *= 2
                while tempo > 180:
                    tempo /= 2

    rms = float(np.mean(energies))
    dynamic = float(np.percentile(energies, 90) / (np.percentile(energies, 20) + 1e-6))
    brightness = float(np.mean(centroids))
    zcr = zero_crossings / frame_count
    energy_norm = float(np.clip(rms / 0.18, 0, 1.25))
    # 高能量曲目容易把半拍误判为一拍，向上折叠到常见舞曲速度
    if tempo < 80 and energy_norm > 0.92:
        tempo *= 2
    brightness_norm = float(np.clip((brightness - 450) / 2500, 0, 1))
    tempo_norm = float(np.clip((tempo - 50) / 130, 0, 1))
    zcr_norm = float(np.clip(zcr / 0.07, 0, 1))
    arousal = float(np.clip(0.04 + 0.42 * tempo_norm + 0.48 * min(energy_norm, 1.0) + 0.06 * brightness_norm, 0, 1))
    if mode == "major":
        mode_valence = 0.90
        valence = 0.76 * mode_valence + 0.10 * (1 - zcr_norm) + 0.08 * brightness_norm + 0.04
    else:
        mode_valence = 0.18
        valence = 0.76 * mode_valence + 0.10 * (1 - zcr_norm) + 0.08 * brightness_norm + 0.02
    valence = float(np.clip(valence - 0.03 * min(dynamic, 4) / 4, 0, 1))
    duration = samples.size / sample_rate
    mood = classify_mood(valence, arousal)
    return {
        "duration": round(float(duration), 2),
        "tempo": round(float(tempo), 1),
        "mode": mode,
        "modeConfidence": round(mode_corr, 3),
        "energy": round(energy_norm, 3),
        "brightness": round(brightness, 1),
        "spectralCentroid": round(brightness, 1),
        "dynamicRange": round(dynamic, 2),
        "zeroCrossRate": round(zcr, 4),
        "valence": round(valence, 3),
        "arousal": round(arousal, 3),
        "mood": mood,
        "chroma": [round(float(v), 4) for v in chroma],
        "analysisVersion": "krumhansl-thayer-v2",
    }


def classify_mood(valence: float, arousal: float) -> str:
    best = "neutral"
    best_distance = 9.0
    for emotion, target in EMOTION_TARGETS.items():
        distance = math.sqrt((valence - target["valence"]) ** 2 + (arousal - target["arousal"]) ** 2)
        if distance < best_distance:
            best = emotion
            best_distance = distance
    return best


def mood_scores_from_features(features: dict) -> dict[str, float]:
    valley, arousal = float(features.get("valence", 0.5)), float(features.get("arousal", 0.45))
    scores = {}
    for emotion, target in EMOTION_TARGETS.items():
        distance = math.hypot(valley - target["valence"], arousal - target["arousal"])
        scores[emotion] = math.exp(-2.8 * distance)
    total = sum(scores.values())
    return {key: round(value / total, 4) for key, value in scores.items()}
