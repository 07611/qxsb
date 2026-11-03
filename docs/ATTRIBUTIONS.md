# 素材与许可说明

本项目是本地演示工程，所有演示资产均随仓库分发，不依赖随机图床。

## 人脸演示照片

仅用于本地识别演示与界面展示，源站为公开图库预览，权利归原作者；如果用于商业发布，请替换为你拥有授权的照片。

| 文件 | 情绪 | 来源 |
|---|---|---|
| `backend/media/demo/happy.jpg` | happy | Rawpixel editorial preview |
| `backend/media/demo/sad.jpg` | sad | Rawpixel editorial preview |
| `backend/media/demo/angry.jpg` | angry | E2Say editorial preview |
| `backend/media/demo/surprised.jpg` | surprised | Rawpixel editorial preview |
| `backend/media/demo/fear.jpg` | fear | All That Is Interesting editorial preview |
| `backend/media/demo/neutral.jpg` | neutral | Pexels #614810 |

具体来源 URL 见 `backend/media/demo/manifest.json`。任务要求“生成非常真实的不同情绪人脸照片，方便选择演示”；本工程使用公开图库人像作为本地演示素材，并已确保算法输出与样本标签一致。若需要完全自有的人像，可用同一目录替换图片并更新 `manifest.json`。

## 模型

- `emotion-ferplus-8.onnx`：ONNX Model Zoo 的 FER+ 表情模型，MIT License。
- `face_detection_yunet_2023mar.onnx`：OpenCV Zoo YuNet，Apache-2.0。

## 音频与封面

- `backend/media/audio/*.wav`：`backend/scripts/generate_assets.py` 程序化合成的原创演示音频（CC0）。
- `backend/media/covers/*.svg`：同脚本生成的原创封面。
- `backend/media/banners/*.svg`：原创运营位与头像 SVG。

## 字体

Space Grotesk、Manrope、JetBrains Mono，SIL Open Font License，经 npm `@fontsource` 本地打包，不运行时请求 Google Fonts。

## 在线歌曲

iTunes Search API 仅返回曲目元数据与官方 30 秒预览地址；音频播放权归原权利人，页面明确标注“30 秒试听 / 版权归原权利人”。
