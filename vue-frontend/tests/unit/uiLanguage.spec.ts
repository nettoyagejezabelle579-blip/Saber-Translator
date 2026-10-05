import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

let stopPrevious: (() => void) | null = null

async function freshModule() {
  stopPrevious?.()
  vi.resetModules()
  const module = await import('@/i18n/uiLanguage')
  stopPrevious = module.stopUiLanguage
  return module
}

function flush() {
  return new Promise(resolve => setTimeout(resolve, 0))
}

describe('interface language', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    document.title = '漫画翻译'
    localStorage.clear()
    window.history.replaceState(null, '', '/')
  })
  afterEach(() => {
    stopPrevious?.()
    document.body.innerHTML = ''
  })

  it('defaults to Traditional Chinese and converts only the characters', async () => {
    document.body.innerHTML = `
      <h1>设置</h1>
      <button title="打开文件夹" aria-label="新建章节">保存</button>
      <span data-no-convert>進撃の巨人 国語版</span>
      <p>文本块对齐：居中</p>`
    const search = document.createElement('input')
    search.placeholder = '搜索书籍'
    search.value = '简体输入不要改'
    document.body.appendChild(search)
    const editor = document.createElement('textarea')
    editor.value = '原文：国语'
    document.body.appendChild(editor)
    const { startUiLanguage, currentUiLanguage } = await freshModule()
    expect(currentUiLanguage()).toBe('zh-TW')
    await startUiLanguage()
    expect(document.documentElement.lang).toBe('zh-TW')
    expect(document.querySelector('h1')!.textContent).toBe('設置')
    const button = document.querySelector('button')!
    expect(button.textContent).toBe('保存')
    expect(button.title).toBe('打開文件夾')
    expect(button.getAttribute('aria-label')).toBe('新建章節')
    const input = search
    expect(input.placeholder).toBe('搜索書籍')
    expect(input.value).toBe('简体输入不要改')
    expect(editor.value).toBe('原文：国语')
    expect(document.querySelector('[data-no-convert]')!.textContent).toBe('進撃の巨人 国語版')
    expect(document.querySelector('p')!.textContent).toBe('文本塊對齊：居中')
    expect(document.title).toBe('漫畫翻譯')

    // 之後才出現或更新的文字也會轉換
    const toast = document.createElement('div')
    toast.textContent = '加载失败，请检查网络'
    document.body.appendChild(toast)
    await flush()
    expect(toast.textContent).toBe('加載失敗，請檢查網絡')
    document.querySelector('h1')!.firstChild!.nodeValue = '默认视频'
    await flush()
    expect(document.querySelector('h1')!.textContent).toBe('默認視頻')
  })

  it('keeps the original Simplified text when Simplified Chinese is chosen', async () => {
    localStorage.setItem('saber.uiLanguage', 'zh-CN')
    document.body.innerHTML = '<h1>设置</h1>'
    const { startUiLanguage } = await freshModule()
    await startUiLanguage()
    expect(document.documentElement.lang).toBe('zh-CN')
    expect(document.querySelector('h1')!.textContent).toBe('设置')
  })

  it('follows ?lang= from the desktop control centre and remembers it', async () => {
    window.history.replaceState(null, '', '/?lang=zh-CN')
    const { startUiLanguage } = await freshModule()
    expect(await startUiLanguage()).toBe('zh-CN')
    expect(localStorage.getItem('saber.uiLanguage')).toBe('zh-CN')
  })
})
