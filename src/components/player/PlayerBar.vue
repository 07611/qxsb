<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePlayerStore } from '@/stores/player'
import { formatDuration } from '@/utils/format'

const player = usePlayerStore()
const { t } = useI18n()
const audioRef = ref(null)

const isOnline = computed(() => player.current?.source === 'itunes')
const sourceLabel = computed(() => (isOnline.value ? t('recommendation.onlineBadge') : t('recommendation.localBadge')))

function togglePlay() {
  if (!player.current) return
  player.toggle()
}

function seek(event) {
  if (!audioRef.value || !player.duration) return
  audioRef.value.currentTime = Number(event.target.value)
}

function onTimeUpdate() {
  if (!audioRef.value) return
  player.setMeta({ currentTime: audioRef.value.currentTime, duration: audioRef.value.duration || 0 })
}

function onLoaded() {
  if (!audioRef.value) return
  player.setMeta({ currentTime: 0, duration: audioRef.value.duration || 0 })
}

function onError() {
  player.reportError(t('player.playFailed'))
}

watch(
  () => player.current?.audioUrl,
  async (url) => {
    player.setMeta({ currentTime: 0, duration: 0 })
    if (!url) return
    await nextTick()
    if (!audioRef.value) return
    audioRef.value.load()
    if (player.isPlaying) {
      audioRef.value.play().catch(() => player.reportError(t('player.playFailed')))
    }
  },
  { immediate: true },
)

watch(
  () => player.isPlaying,
  (playing) => {
    if (!audioRef.value) return
    if (playing) {
      audioRef.value.play().catch(() => player.reportError(t('player.playFailed')))
    } else {
      audioRef.value.pause()
    }
  },
)

watch(
  () => player.volume,
  (value) => {
    if (audioRef.value) audioRef.value.volume = value
  },
  { immediate: true },
)
</script>

<template>
  <transition name="player-rise">
    <aside v-if="player.current" class="player-shell" :aria-label="$t('extra.player')">
      <audio
        ref="audioRef"
        :src="player.current.audioUrl"
        preload="metadata"
        @timeupdate="onTimeUpdate"
        @loadedmetadata="onLoaded"
        @ended="player.next()"
        @error="onError"
      />
      <div class="player-progress">
        <input
          type="range"
          min="0"
          :max="player.duration || 0"
          step="0.1"
          :value="player.currentTime"
          :aria-label="t('player.nowPlaying')"
          @input="seek"
        />
        <span class="progress-fill" :style="{ width: `${player.progress}%` }"></span>
      </div>
      <div class="player-content">
        <div class="now-main">
          <div class="cover-wrap" :class="{ playing: player.isPlaying }">
            <img
              v-if="player.current.coverUrl"
              :src="player.current.coverUrl"
              alt=""
              width="52"
              height="52"
            />
            <div class="equalizer" aria-hidden="true">
              <span></span><span></span><span></span>
            </div>
          </div>
          <div class="track-meta">
            <div class="now-label">{{ t('player.nowPlaying') }} · {{ sourceLabel }}</div>
            <div class="track-title">{{ player.current.title }}</div>
            <div class="track-artist">{{ player.current.artist }}</div>
          </div>
        </div>
        <div class="controls">
          <button class="ctrl-btn small-hide" :aria-label="t('player.previous')" @click="player.previous()">
            <el-icon><ArrowLeftBold /></el-icon>
          </button>
          <button class="ctrl-btn main" :aria-label="player.isPlaying ? t('recommendation.pause') : t('recommendation.play')" @click="togglePlay">
            <el-icon :size="19"><VideoPause v-if="player.isPlaying" /><VideoPlay v-else /></el-icon>
          </button>
          <button class="ctrl-btn small-hide" :aria-label="t('player.next')" @click="player.next()">
            <el-icon><ArrowRightBold /></el-icon>
          </button>
        </div>
        <div class="right-controls">
          <span class="time mono">{{ formatDuration(player.currentTime) }} / {{ formatDuration(player.duration || player.current.duration) }}</span>
          <div class="volume">
            <el-icon><Headset /></el-icon>
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              :value="player.volume"
              :aria-label="t('player.volume')"
              @input="player.setVolume($event.target.value)"
            />
          </div>
          <button class="ctrl-btn" :aria-label="t('player.close')" @click="player.close()">
            <el-icon><Close /></el-icon>
          </button>
        </div>
      </div>
      <p v-if="isOnline" class="online-note">{{ t('player.onlineNotice') }}</p>
      <p v-if="player.error" class="player-error">{{ player.error }}</p>
    </aside>
  </transition>
</template>

<style scoped>
.player-shell {
  position: fixed;
  z-index: 90;
  left: 50%;
  bottom: 20px;
  transform: translateX(-50%);
  width: min(900px, calc(100% - 32px));
  border: 1px solid var(--line);
  border-radius: 14px;
  background: color-mix(in srgb, var(--surface) 92%, transparent);
  backdrop-filter: blur(22px) saturate(140%);
  box-shadow: 0 20px 60px rgba(26, 26, 28, 0.14);
  overflow: hidden;
}
.player-content {
  display: grid;
  grid-template-columns: 1.4fr auto 1fr;
  align-items: center;
  gap: 18px;
  padding: 10px 13px;
}
.now-main {
  display: flex;
  align-items: center;
  gap: 11px;
  min-width: 0;
}
.cover-wrap {
  position: relative;
  width: 52px;
  height: 52px;
  border-radius: 9px;
  overflow: hidden;
  flex-shrink: 0;
  background: var(--surface-2);
}
.cover-wrap img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.cover-wrap::after {
  content: '';
  position: absolute;
  inset: 0;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: inherit;
}
.equalizer {
  display: none;
  position: absolute;
  inset: 0;
  align-items: flex-end;
  justify-content: center;
  gap: 3px;
  padding-bottom: 13px;
  background: rgba(10, 10, 14, 0.44);
  backdrop-filter: blur(2px);
}
.cover-wrap.playing .equalizer {
  display: flex;
}
.equalizer span {
  width: 3px;
  height: 12px;
  background: #fff;
  animation: eq 0.9s ease-in-out infinite;
}
.equalizer span:nth-child(2) {
  height: 20px;
  animation-delay: 0.16s;
}
.equalizer span:nth-child(3) {
  height: 8px;
  animation-delay: 0.3s;
}
@keyframes eq {
  0%,
  100% {
    transform: scaleY(0.4);
  }
  50% {
    transform: scaleY(1);
  }
}
.track-meta {
  min-width: 0;
}
.now-label {
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.1em;
  color: var(--muted);
  text-transform: uppercase;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.track-title {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 570;
  letter-spacing: -0.02em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.track-artist {
  font-size: 11px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.controls {
  display: flex;
  align-items: center;
  gap: 6px;
}
.ctrl-btn {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--muted);
  transition: all 150ms;
}
.ctrl-btn:hover {
  background: var(--surface-2);
  color: var(--ink);
}
.ctrl-btn.main {
  width: 42px;
  height: 42px;
  background: var(--ink);
  color: var(--bg);
}
.ctrl-btn.main:hover {
  transform: scale(1.04);
  background: var(--accent);
  color: #fff;
}
.right-controls {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}
.time {
  font-size: 9px;
  color: var(--muted);
  white-space: nowrap;
}
.volume {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
}
.volume input {
  width: 70px;
  accent-color: var(--accent);
}
.player-progress {
  position: relative;
  height: 2px;
  background: var(--line);
}
.player-progress::before {
  content: '';
  position: absolute;
  inset: 0;
}
.player-progress input {
  position: absolute;
  inset: -5px 0;
  width: 100%;
  height: 12px;
  opacity: 0;
  cursor: pointer;
  z-index: 2;
}
.progress-fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: var(--accent);
  pointer-events: none;
}
.online-note {
  position: absolute;
  right: 112px;
  top: 3px;
  font-size: 8px;
  color: var(--muted-2);
  pointer-events: none;
}
.player-error {
  position: absolute;
  bottom: 3px;
  left: 14px;
  font-size: 9px;
  color: var(--danger);
}
.player-rise-enter-active,
.player-rise-leave-active {
  transition:
    opacity 200ms ease,
    transform 260ms var(--ease);
}
.player-rise-enter-from,
.player-rise-leave-to {
  opacity: 0;
  transform: translate(-50%, 16px);
}
@media (max-width: 760px) {
  .player-shell {
    bottom: 80px;
    width: calc(100% - 20px);
    border-radius: 12px;
  }
  .player-content {
    grid-template-columns: 1fr auto;
    gap: 10px;
    padding: 8px 10px;
  }
  .controls {
    order: 2;
  }
  .right-controls {
    display: none;
  }
  .cover-wrap {
    width: 42px;
    height: 42px;
  }
  .track-title {
    font-size: 13px;
  }
  .online-note {
    display: none;
  }
}
</style>
