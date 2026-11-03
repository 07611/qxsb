<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatDuration, emotionColor } from '@/utils/format'

const props = defineProps({
  track: { type: Object, required: true },
  index: { type: Number, default: 0 },
  playing: Boolean,
  saved: Boolean,
  rating: { type: Number, default: 0 },
  compact: Boolean,
})
const emit = defineEmits(['play', 'favorite', 'rate'])
const { t } = useI18n()

const isLocal = computed(() => props.track.source === 'local')
const bpm = computed(() => props.track.audioFeatures?.tempo || props.track.bpm)
const mode = computed(() => props.track.audioFeatures?.mode)
const accent = computed(() => emotionColor(props.track.mood))
</script>

<template>
  <article class="track-row" :class="{ compact, playing, rated: rating !== 0 }">
    <button class="play-hit" :aria-label="playing ? t('recommendation.pause') : t('recommendation.play')" @click="emit('play', track)">
      <span class="track-index mono">{{ String(index + 1).padStart(2, '0') }}</span>
      <span class="track-cover">
        <img
          v-if="track.coverUrl"
          :src="track.coverUrl"
          :alt="track.title"
          width="62"
          height="62"
          loading="lazy"
        />
        <span v-else class="cover-fallback" :style="{ background: accent }">{{ track.title?.slice(0, 1) }}</span>
        <span class="cover-play" :class="{ visible: playing }">
          <el-icon :size="15"><VideoPause v-if="playing" /><VideoPlay v-else /></el-icon>
        </span>
      </span>
      <span class="track-main">
        <span class="track-top">
          <strong>{{ track.title }}</strong>
          <span class="source-pill" :class="{ online: !isLocal }">{{ isLocal ? t('recommendation.localBadge') : 'iTunes' }}</span>
        </span>
        <span class="track-sub">{{ track.artist }}<template v-if="track.album"> · {{ track.album }}</template></span>
        <span v-if="!compact && track.reason" class="track-reason">{{ track.reason }}</span>
      </span>
    </button>

    <div class="track-meta">
      <span v-if="bpm" class="meta-chip mono">{{ bpm }} BPM</span>
      <span v-if="mode" class="meta-chip">{{ mode === 'major' ? t('recommendation.major') : t('recommendation.minor') }}</span>
      <span class="duration mono">{{ formatDuration(track.duration) }}</span>
    </div>

    <div class="track-actions">
      <button
        v-if="isLocal"
        class="action-btn"
        :class="{ on: rating === 1 }"
        :aria-label="t('recommendation.like')"
        @click.stop="emit('rate', track, 1)"
      >
        <el-icon :size="15"><Top /></el-icon>
      </button>
      <button
        v-if="isLocal"
        class="action-btn"
        :class="{ off: rating === -1 }"
        :aria-label="t('recommendation.dislike')"
        @click.stop="emit('rate', track, -1)"
      >
        <el-icon :size="15"><Bottom /></el-icon>
      </button>
      <button
        v-if="isLocal"
        class="action-btn favorite"
        :class="{ on: saved }"
        :aria-label="saved ? t('recommendation.unfavorite') : t('recommendation.favorite')"
        @click.stop="emit('favorite', track)"
      >
        <el-icon :size="15"><StarFilled v-if="saved" /><Star v-else /></el-icon>
      </button>
      <button class="play-inline" :aria-label="t('recommendation.play')" @click.stop="emit('play', track)">
        <el-icon :size="16"><VideoPlay /></el-icon>
      </button>
    </div>
  </article>
</template>

<style scoped>
.track-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
  transition: all 180ms var(--ease);
}
.track-row:hover {
  border-color: var(--line-strong);
  background: color-mix(in srgb, var(--surface) 80%, var(--surface-2));
}
.track-row.playing {
  border-color: color-mix(in srgb, var(--accent) 42%, var(--line));
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 8%, transparent);
}
.track-row.rated {
  opacity: 0.82;
}
.play-hit {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  text-align: left;
  background: transparent;
  border: 0;
  padding: 0;
  color: inherit;
  min-height: 62px;
}
.track-index {
  color: var(--muted-2);
  font-size: 9px;
  width: 16px;
  flex-shrink: 0;
}
.track-cover {
  position: relative;
  width: 62px;
  height: 62px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
  background: var(--surface-2);
}
.track-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.cover-fallback {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  font-family: var(--font-display);
  font-size: 24px;
  color: rgba(255, 255, 255, 0.8);
}
.cover-play {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #fff;
  background: rgba(10, 10, 15, 0.34);
  opacity: 0;
  transition: opacity 160ms;
}
.track-cover:hover .cover-play,
.cover-play.visible {
  opacity: 1;
}
.track-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.track-top {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
}
.track-top strong {
  font-size: 14px;
  font-weight: 670;
  letter-spacing: -0.012em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-pill {
  font-family: var(--font-mono);
  font-size: 7px;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: 3px;
  padding: 2px 4px;
  flex-shrink: 0;
}
.source-pill.online {
  color: var(--signal);
  background: var(--signal-soft);
}
.track-sub {
  font-size: 11.5px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.track-reason {
  margin-top: 4px;
  font-size: 10.5px;
  line-height: 1.5;
  color: var(--muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.track-meta {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
}
.meta-chip {
  font-size: 8px;
  color: var(--muted);
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 3px 5px;
  white-space: nowrap;
  background: var(--surface-2);
}
.duration {
  color: var(--muted-2);
  font-size: 8px;
  margin-left: 3px;
}
.track-actions {
  display: flex;
  gap: 1px;
  flex-shrink: 0;
}
.action-btn {
  width: 30px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--muted-2);
  transition: all 140ms;
}
.action-btn:hover {
  color: var(--ink);
  background: var(--surface-2);
}
.action-btn.on {
  color: var(--accent);
}
.action-btn.off {
  color: var(--signal);
}
.action-btn.favorite.on {
  color: var(--happy);
}
.play-inline {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
  display: grid;
  place-items: center;
  margin-left: 3px;
}
.play-inline:hover {
  background: var(--ink);
  color: var(--bg);
}
.track-row.compact {
  padding: 8px;
}
.track-row.compact .track-cover {
  width: 48px;
  height: 48px;
}
.track-row.compact .track-reason {
  display: none;
}
@media (max-width: 760px) {
  .track-index,
  .track-meta {
    display: none;
  }
  .track-actions .action-btn:not(.favorite) {
    display: none;
  }
  .track-cover {
    width: 54px;
    height: 54px;
  }
  .track-top strong {
    font-size: 13px;
  }
  .track-reason {
    -webkit-line-clamp: 1;
  }
  .play-hit {
    gap: 9px;
  }
}
</style>
