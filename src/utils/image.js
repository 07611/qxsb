import { uploadApi } from '@/services/api'

const MAX_IMAGE_BYTES = 5 * 1024 * 1024
export const ACCEPTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']

export function validateImage(file) {
  if (!file) return '请选择图片'
  if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) return '仅支持 JPG / PNG / WebP'
  if (file.size > MAX_IMAGE_BYTES) return '图片不能超过 5MB'
  return ''
}

export function loadImageElement(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const image = new Image()
    image.onload = () => {
      URL.revokeObjectURL(url)
      resolve(image)
    }
    image.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('图片无法解析'))
    }
    image.src = url
  })
}

export async function compressImage(file, { maxSide = 1280, quality = 0.86, square = false } = {}) {
  const error = validateImage(file)
  if (error) throw new Error(error)
  const image = await loadImageElement(file)
  let sw = image.naturalWidth
  let sh = image.naturalHeight
  if (square) {
    const side = Math.min(sw, sh)
    sw = side
    sh = side
  }
  const scale = Math.min(1, maxSide / Math.max(sw, sh))
  const width = Math.max(1, Math.round(sw * scale))
  const height = Math.max(1, Math.round(sh * scale))
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  context.imageSmoothingQuality = 'high'
  if (square) {
    context.drawImage(image, (image.naturalWidth - sw) / 2, (image.naturalHeight - sh) / 2, sw, sh, 0, 0, width, height)
  } else {
    context.drawImage(image, 0, 0, width, height)
  }
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality))
  if (!blob) throw new Error('图片压缩失败')
  const name = (file.name || 'image').replace(/\.[^.]+$/, '') + '.jpg'
  return new File([blob], name, { type: 'image/jpeg', lastModified: Date.now() })
}

export function captureFrame(video, { maxSide = 1280, quality = 0.86 } = {}) {
  const width = video.videoWidth
  const height = video.videoHeight
  if (!width || !height) throw new Error('视频画面尚未准备好')
  const scale = Math.min(1, maxSide / Math.max(width, height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(width * scale)
  canvas.height = Math.round(height * scale)
  const context = canvas.getContext('2d')
  context.drawImage(video, 0, 0, canvas.width, canvas.height)
  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(new File([blob], `frame-${Date.now()}.jpg`, { type: 'image/jpeg' })), 'image/jpeg', quality)
  })
}

export async function uploadImage(file, bizType = 'item_cover') {
  const compressed = await compressImage(file, { maxSide: 1600, quality: 0.88 })
  const presign = await uploadApi.presign({
    filename: compressed.name,
    mime: compressed.type,
    size: compressed.size,
    bizType,
  })
  await uploadApi.put(presign.data.uploadUrl, compressed, compressed.type)
  const attachment = await uploadApi.register({
    uploadToken: presign.data.uploadToken,
    bizType,
  })
  return attachment.data.attachment
}

export function fileToObjectUrl(file) {
  return URL.createObjectURL(file)
}
