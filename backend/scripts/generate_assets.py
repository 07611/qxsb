"""生成项目内置的原创演示曲目与封面（可重复执行，不使用第三方版权素材）。

音频由简单加法合成器离线生成，保存为 WAV，便于服务器用 wave + numpy
做真实 BPM / chroma / 调式分析。运行：
    python backend/scripts/generate_assets.py
"""

from __future__ import annotations

import json
import math
import random
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SR = 22050
ROOT = Path(__file__).resolve().parents[2]
AUDIO = ROOT / "backend" / "media" / "audio"
COVERS = ROOT / "backend" / "media" / "covers"
BANNERS = ROOT / "backend" / "media" / "banners"

MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]
NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
MODE_COLORS = {
    "happy": ("#F3A43B", "#E8552F", "#FFE8A8"),
    "sad": ("#5B7DB1", "#2E3A56", "#D9E2F1"),
    "angry": ("#E8552F", "#7A1F2B", "#FFD0C0"),
    "fear": ("#4F8C86", "#1E3336", "#CDE7E2"),
    "surprised": ("#9B6BD6", "#E8A23B", "#F1E6FF"),
    "neutral": ("#8C897F", "#4A4944", "#EFEDE6"),
}


@dataclass
class Composition:
    slug: str
    title: str
    title_en: str
    artist: str
    album: str
    mood: str
    bpm: float
    root: str
    mode: str
    bars: int = 8
    seed: int = 1
    texture: str = "soft"


TRACKS = [
    Composition("morning-drift", "晨光漫游", "Morning Drift", "Moodwave Studio", "Slow Light", "happy", 112, "C", "major", 10, 11, "bright"),
    Composition("lemon-static", "柠檬气泡", "Lemon Static", "Soft Relay", "Small Joys", "happy", 124, "G", "major", 9, 12, "pluck"),
    Composition("rain-window", "雨窗独白", "Rain Window", "Nocturne Lab", "Rooms at Dusk", "sad", 68, "A", "minor", 8, 21, "soft"),
    Composition("unsent-letter", "未寄出的信", "Unsent Letter", "Nocturne Lab", "Rooms at Dusk", "sad", 74, "D", "minor", 9, 22, "felt"),
    Composition("red-shift", "红移", "Red Shift", "Static Youth", "Pressure Lines", "angry", 138, "D", "minor", 10, 31, "drive"),
    Composition("undertow", "暗涌", "Undertow", "Static Youth", "Pressure Lines", "angry", 126, "E", "minor", 9, 32, "drive"),
    Composition("hover", "悬停", "Hover", "Nocturne Lab", "Unsteady Air", "fear", 82, "E", "minor", 8, 41, "uneasy"),
    Composition("little-spark", "微光惊起", "Little Spark", "Soft Relay", "Small Joys", "surprised", 120, "F", "major", 9, 51, "spark"),
    Composition("still-water", "静海", "Still Water", "Moodwave Studio", "Slow Light", "neutral", 72, "C", "major", 8, 61, "soft"),
    Composition("white-noise-cafe", "白噪咖啡馆", "White Noise Cafe", "Soft Relay", "Small Joys", "neutral", 88, "F", "major", 8, 62, "lofi"),
    Composition("electric-bloom", "电光开花", "Electric Bloom", "Moodwave Studio", "Flash Frames", "surprised", 152, "D", "major", 10, 71, "spark"),
    Composition("slow-cafe", "慢速咖啡馆", "Slow Cafe", "Moodwave Studio", "Slow Light", "neutral", 58, "F", "major", 7, 72, "soft"),
]
PROGRESSIONS = {
    "major": [[0, 4, 5, 3], [0, 5, 3, 4], [0, 3, 5, 4]],
    "minor": [[0, 5, 2, 6], [0, 3, 5, 4], [0, 6, 5, 4]],
}


def midi_freq(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def note_midi(root: str, scale: str, degree: int, octave: int = 4) -> int:
    pattern = MAJOR if scale == "major" else MINOR
    root_midi = 12 * (octave + 1) + NOTE[root]
    return root_midi + pattern[degree % 7] + 12 * (degree // 7)


def adsr(length: int, attack: float, decay: float, sustain: float, release: float) -> np.ndarray:
    a = max(1, int(length * attack))
    d = max(1, int(length * decay))
    r = max(1, int(length * release))
    s = max(1, length - a - d - r)
    if a + d + r >= length:
        a = max(1, length // 5)
        d = max(1, length // 5)
        r = max(1, length // 4)
        s = max(1, length - a - d - r)
    return np.concatenate(
        [
            np.linspace(0, 1, a, endpoint=False),
            np.linspace(1, sustain, d, endpoint=False),
            np.full(s, sustain),
            np.linspace(sustain, 0, r),
        ]
    )[:length]


def oscillator(freq: float, length: int, kind: str = "sine", detune: float = 0.0) -> np.ndarray:
    t = np.arange(length) / SR
    f = freq * (1 + detune)
    if kind == "sine":
        return np.sin(2 * np.pi * f * t)
    if kind == "triangle":
        return sum(((-1) ** k) * np.sin(2 * np.pi * f * (2 * k + 1) * t) / (2 * k + 1) ** 2 for k in range(4)) * 1.2
    if kind == "saw":
        return sum(np.sin(2 * np.pi * f * n * t) / n for n in range(1, 7)) * 0.55
    if kind == "soft":
        return np.sin(2 * np.pi * f * t) + 0.22 * np.sin(2 * np.pi * f * 2 * t) + 0.08 * np.sin(2 * np.pi * f * 3 * t)
    return np.sin(2 * np.pi * f * t)


def place(buffer: np.ndarray, sound: np.ndarray, start: int, gain: float = 1.0) -> None:
    if start >= buffer.size:
        return
    end = min(buffer.size, start + sound.size)
    buffer[start:end] += sound[: end - start] * gain


def reverb(signal: np.ndarray, mood: str) -> np.ndarray:
    out = signal.copy()
    delays = [0.09, 0.17, 0.29] if mood in {"sad", "fear", "neutral"} else [0.06, 0.13, 0.21]
    for index, delay in enumerate(delays):
        samples = int(SR * delay)
        tail = np.zeros_like(signal)
        tail[samples:] = signal[:-samples] * (0.24 - index * 0.055)
        out += tail
    return out


def synth(comp: Composition) -> np.ndarray:
    random.seed(comp.seed)
    np.random.seed(comp.seed)
    beat = 60 / comp.bpm
    bar = beat * 4
    total = int((comp.bars + 1.5) * bar * SR)
    mix = np.zeros(total, dtype=np.float64)
    pattern = MAJOR if comp.mode == "major" else MINOR
    progression = PROGRESSIONS[comp.mode][comp.seed % 3]
    chord_bars = 2
    chord_duration = int(bar * chord_bars * SR)
    chord_count = math.ceil(comp.bars / chord_bars)

    for chord_index in range(chord_count):
        degree = progression[chord_index % len(progression)]
        start = int(chord_index * chord_duration)
        triad = [note_midi(comp.root, comp.mode, degree + offset) for offset in (0, 2, 4)]
        if comp.texture == "uneasy":
            triad[1] += 1  # 小二度色彩，增加不安定感
        # pad
        for index, midi in enumerate(triad):
            freq = midi_freq(midi - 12 if comp.texture in {"soft", "felt"} else midi)
            length = int(chord_duration * 1.02)
            env = adsr(length, 0.16, 0.2, 0.58, 0.35)
            tone = oscillator(freq, length, "soft", detune=0.002) * 0.17
            tone += oscillator(freq, length, "triangle", detune=-0.002) * 0.05
            place(mix, tone * env, start, 0.6 if index else 0.78)
        # bass
        bass_midi = note_midi(comp.root, comp.mode, degree) - 24
        for beat_index in range(chord_bars * 4):
            if comp.texture == "soft" and beat_index % 2:
                continue
            length = int(beat * SR * (0.92 if comp.texture == "drive" else 1.4))
            env = adsr(length, 0.02, 0.15, 0.5, 0.3)
            tone = oscillator(midi_freq(bass_midi), length, "saw" if comp.texture == "drive" else "sine") * 0.24
            place(mix, tone * env, start + int(beat_index * beat * SR), 0.95)
        # arpeggio
        arp_step = beat / (2 if comp.texture in {"bright", "spark", "pluck"} else 1)
        steps = int((bar * chord_bars) / arp_step)
        for step in range(steps):
            if comp.texture in {"soft", "felt"} and step % 2:
                continue
            note_index = [0, 2, 4, 2][step % 4]
            midi = note_midi(comp.root, comp.mode, degree + note_index, octave=5)
            if comp.texture == "spark" and step % 4 == 3:
                midi += 12
            length = int(arp_step * SR * 0.9)
            env = adsr(length, 0.01, 0.2, 0.18, 0.45)
            timbre = "pluck" if comp.texture == "pluck" else ("triangle" if comp.texture in {"bright", "spark"} else "sine")
            tone = oscillator(midi_freq(midi), length, timbre) * (0.12 if comp.texture != "drive" else 0.05)
            place(mix, tone * env, start + int(step * arp_step * SR), 0.9)

    # melody
    melody_step = beat * 2
    melody_length = int((comp.bars * bar) / melody_step)
    previous = 3
    for index in range(melody_length):
        if random.random() < (0.5 if comp.texture in {"soft", "felt"} else 0.28):
            continue
        move = random.choice([-2, -1, 0, 1, 2]) if comp.texture != "spark" else random.choice([-3, -1, 1, 3, 4])
        previous = max(0, min(7, previous + move))
        midi = note_midi(comp.root, comp.mode, previous, octave=5) + (12 if comp.mood == "happy" and index % 4 == 2 else 0)
        length = int(melody_step * SR * (0.8 if comp.texture in {"bright", "spark"} else 1.2))
        env = adsr(length, 0.03, 0.18, 0.38, 0.4)
        tone = oscillator(midi_freq(midi), length, "pluck" if comp.texture in {"bright", "pluck", "spark"} else "soft")
        place(mix, tone * env, int(index * melody_step * SR) + int(beat * 0.16 * SR), 0.55)

    # 打击乐
    for beat_index in range(int(comp.bars * 4)):
        position = int(beat_index * beat * SR)
        if comp.texture in {"drive", "spark"} or (comp.texture in {"bright", "pluck", "lofi"} and beat_index % 2 == 0):
            length = int(0.14 * SR)
            t = np.arange(length) / SR
            kick = np.sin(2 * np.pi * (85 * np.exp(-t * 18) + 42) * t) * np.exp(-t * 15)
            place(mix, kick, position, 0.48 if comp.texture != "drive" else 0.65)
        if comp.texture in {"drive", "spark", "lofi"} and beat_index % 2 == 1:
            length = int(0.08 * SR)
            noise = np.random.randn(length) * np.exp(-np.arange(length) / SR * 38)
            place(mix, noise, position, 0.075 if comp.texture == "lofi" else 0.12)
    if comp.texture == "uneasy":
        tremolo = 0.75 + 0.25 * np.sin(2 * np.pi * 5.2 * np.arange(total) / SR)
        mix *= tremolo

    if comp.texture == "drive":
        mix = np.tanh(mix * 1.8) * 0.72
    mix = reverb(mix, comp.mood)

    # 简单移动平均低通，削弱数字高频（向量化，避免逐样本循环）
    window = 9 if comp.mood != "angry" else 4
    mix = np.convolve(mix, np.ones(window, dtype=np.float64) / window, mode="same")

    fade_in = int(0.04 * SR)
    fade_out = int(1.2 * SR)
    mix[:fade_in] *= np.linspace(0, 1, fade_in)
    mix[-fade_out:] *= np.linspace(1, 0, fade_out)
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = mix / peak * 0.88
    return mix.astype(np.float32)


def write_wav(path: Path, samples: np.ndarray) -> None:
    pcm = np.clip(samples, -1, 1)
    pcm = (pcm * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        handle.writeframes(pcm.tobytes())


def cover_svg(comp: Composition) -> str:
    c1, c2, c3 = MODE_COLORS[comp.mood]
    seed = comp.seed
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800" viewBox="0 0 800 800">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{c1}"/><stop offset=".55" stop-color="{c2}"/><stop offset="1" stop-color="#15151A"/>
    </linearGradient>
    <radialGradient id="glow" cx=".3" cy=".2" r=".75">
      <stop offset="0" stop-color="{c3}" stop-opacity=".72"/><stop offset="1" stop-color="{c3}" stop-opacity="0"/>
    </radialGradient>
    <filter id="blur"><feGaussianBlur stdDeviation="18"/></filter>
  </defs>
  <rect width="800" height="800" fill="url(#g)"/>
  <rect width="800" height="800" fill="url(#glow)"/>
  <g opacity=".52" filter="url(#blur)">
    <circle cx="{160 + seed * 9 % 260}" cy="{590 - seed * 5 % 190}" r="{110 + seed % 90}" fill="{c3}" opacity=".4"/>
    <circle cx="{610 - seed * 3 % 180}" cy="{200 + seed * 7 % 160}" r="{80 + seed % 110}" fill="{c1}" opacity=".35"/>
  </g>
  <g fill="none" stroke="{c3}" stroke-opacity=".48" stroke-width="2">
    <path d="M60 {420 + seed % 80} C 190 {280 + seed * 3 % 120}, 310 {560 - seed * 2 % 100}, 440 {390 + seed * 4 % 90} S 680 {310 + seed % 140}, 750 {400 + seed * 2 % 90}"/>
    <path d="M40 {500 - seed % 80} C 200 {620 - seed * 2 % 100}, 390 {340 + seed % 80}, 540 {470 - seed * 3 % 110} S 720 {540 - seed % 60}, 780 {430 + seed % 80}" stroke-opacity=".22"/>
  </g>
  <g font-family="Georgia, serif" fill="#fff">
    <text x="62" y="92" font-size="17" letter-spacing="7" opacity=".7">MOODWAVE / {comp.mood.upper()}</text>
    <text x="62" y="680" font-size="62" opacity=".96">{comp.title}</text>
    <text x="64" y="724" font-size="22" opacity=".65">{comp.title_en} — {comp.artist}</text>
  </g>
  <rect x="62" y="592" width="46" height="4" rx="2" fill="{c3}" opacity=".8"/>
</svg>"""


def banner_svgs() -> dict[str, str]:
    return {
        "banner-hero.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="500" viewBox="0 0 1600 500">
<defs><linearGradient id="a" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#F6F3EA"/><stop offset=".55" stop-color="#E8E4F5"/><stop offset="1" stop-color="#F5DED3"/></linearGradient><radialGradient id="b" cx=".75" cy=".2" r=".6"><stop stop-color="#5B5BD6" stop-opacity=".28"/><stop offset="1" stop-color="#5B5BD6" stop-opacity="0"/></radialGradient></defs>
<rect width="1600" height="500" fill="url(#a)"/><rect width="1600" height="500" fill="url(#b)"/>
<g fill="none" stroke="#5B5BD6" stroke-opacity=".35"><path d="M850 320c80-180 130 160 210-20s170 40 260-80 160 80 240-50" stroke-width="2"/><path d="M850 360c90-140 140 120 220-30s160 20 250-90 150 60 230-20" stroke-width="1"/></g>
<circle cx="1260" cy="250" r="150" fill="#fff" opacity=".28"/><circle cx="1310" cy="210" r="80" fill="#fff" opacity=".35"/>
<text x="80" y="220" font-family="Georgia,serif" font-size="62" fill="#1A1A1C">让旋律回应此刻的表情</text>
<text x="82" y="272" font-family="Arial,sans-serif" font-size="20" fill="#6B6B72">本地人脸情绪识别 · Krumhansl 曲调分析 · 可解释推荐</text>
<text x="82" y="326" font-family="monospace" font-size="13" letter-spacing="5" fill="#5B5BD6">MOODWAVE / EMOTION TO SOUND</text>
</svg>""",
        "banner-arch.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="500" viewBox="0 0 1600 500">
<defs><linearGradient id="a" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#1D1D24"/><stop offset="1" stop-color="#3A3430"/></linearGradient></defs>
<rect width="1600" height="500" fill="url(#a)"/><path d="M0 430C260 280 390 180 710 260s470 210 890 40v200H0z" fill="#E8552F" opacity=".18"/>
<g fill="none" stroke="#FBFAF7" stroke-opacity=".4"><circle cx="1120" cy="250" r="130"/><circle cx="1120" cy="250" r="96"/><circle cx="1120" cy="250" r="62"/></g>
<text x="80" y="220" font-family="Georgia,serif" font-size="58" fill="#FBFAF7">六种情绪，六条声场路径</text>
<text x="82" y="274" font-family="Arial,sans-serif" font-size="20" fill="#C9C4BA">从表情到曲调，每一个推荐理由都可以被解释。</text>
</svg>""",
        "banner-night.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="500" viewBox="0 0 1600 500">
<defs><linearGradient id="a" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#122D30"/><stop offset="1" stop-color="#334D45"/></linearGradient><radialGradient id="b" cx=".2" cy=".4" r=".5"><stop stop-color="#9BD6C8" stop-opacity=".3"/><stop offset="1" stop-color="#9BD6C8" stop-opacity="0"/></radialGradient></defs>
<rect width="1600" height="500" fill="url(#a)"/><rect width="1600" height="500" fill="url(#b)"/>
<g stroke="#CDE7E2" stroke-opacity=".25" fill="none"><path d="M0 350c140 0 140-90 280-90s140 110 280 110 140-160 280-160 140 120 280 120 140-60 260-60 140 30 220 20"/><path d="M0 390c140 0 140-90 280-90s140 110 280 110 140-160 280-160 140 120 280 120 140-60 260-60 140 30 220 20" stroke-opacity=".1"/></g>
<text x="80" y="220" font-family="Georgia,serif" font-size="58" fill="#F3F0E8">夜晚的更慢一些</text>
<text x="82" y="274" font-family="Arial,sans-serif" font-size="20" fill="#B9CDC7">夜间模式与低唤醒歌单，留给那些不想被打扰的时刻。</text>
</svg>""",
        "share-default.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="600" viewBox="0 0 1200 600">
<defs><linearGradient id="a" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#5B5BD6"/><stop offset="1" stop-color="#E8552F"/></linearGradient></defs>
<rect width="1200" height="600" fill="#FBFAF7"/><circle cx="900" cy="180" r="250" fill="url(#a)" opacity=".18"/><path d="M80 390c90-180 130 80 230-60s160 40 260-60 140 90 230-20 120 30 220-30" fill="none" stroke="url(#a)" stroke-width="3"/>
<text x="80" y="240" font-family="Georgia,serif" font-size="58" fill="#1A1A1C">让旋律回应此刻的表情</text><text x="82" y="292" font-family="monospace" font-size="16" letter-spacing="5" fill="#6B6B72">MOODWAVE / 心绪声场</text>
</svg>""",
    }


def main() -> None:
    AUDIO.mkdir(parents=True, exist_ok=True)
    COVERS.mkdir(parents=True, exist_ok=True)
    BANNERS.mkdir(parents=True, exist_ok=True)
    manifest = []
    for comp in TRACKS:
        print("synthesizing", comp.slug)
        samples = synth(comp)
        audio_path = AUDIO / f"{comp.slug}.wav"
        write_wav(audio_path, samples)
        cover_path = COVERS / f"{comp.slug}.svg"
        cover_path.write_text(cover_svg(comp), encoding="utf-8")
        manifest.append(
            {
                "slug": comp.slug,
                "title": comp.title,
                "titleEn": comp.title_en,
                "artist": comp.artist,
                "album": comp.album,
                "mood": comp.mood,
                "bpm": comp.bpm,
                "mode": comp.mode,
                "audio": f"audio/{comp.slug}.wav",
                "cover": f"covers/{comp.slug}.svg",
                "licenseNote": "Moodwave 程序化原创演示音频（CC0）",
            }
        )
    (AUDIO.parent / "tracks.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, svg in banner_svgs().items():
        (BANNERS / name).write_text(svg, encoding="utf-8")
    print(f"generated {len(TRACKS)} tracks")


if __name__ == "__main__":
    main()
