import { describe, expect, it } from 'vitest'
import { formatDuration, parseUserIds, truncate } from '../../src/utils/format'
import zhCN from '../../src/i18n/zh-CN'
import enUS from '../../src/i18n/en-US'

describe('format utilities', () => {
  it('formats durations without negative time', () => {
    expect(formatDuration(65)).toBe('1:05')
    expect(formatDuration(-1)).toBe('0:00')
    expect(formatDuration(3599)).toBe('59:59')
  })

  it('truncates long copy safely', () => {
    expect(truncate('abcdefghij', 4)).toBe('abcd…')
    expect(truncate('abc', 4)).toBe('abc')
  })

  it('parses comma-separated ids and drops invalid entries', () => {
    expect(parseUserIds('1, 2, x, -3, 4')).toEqual([1, 2, 4])
  })
})

describe('language packs', () => {
  it('keeps both locales structurally usable', () => {
    expect(zhCN.nav.home).toBeTruthy()
    expect(enUS.nav.home).toBeTruthy()
    expect(enUS.auth.emailPlaceholder).toContain("'@'")
    expect(zhCN.emotions.happy).not.toBe(enUS.emotions.happy)
  })
})
