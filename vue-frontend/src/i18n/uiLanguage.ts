/**
 * 介面語言：預設繁體中文（台灣），可切換回简体中文。
 *
 * 介面原文是简体中文。選擇 zh-TW 時，用 OpenCC（cn → twp，含台灣用語：设置→設定、
 * 文件→檔案、加载→載入）把畫面上的文字節點與 placeholder / title / aria-label / alt
 * 即時轉成繁體；Vue 之後更新的文字也會被轉換。
 *
 * 不轉換：輸入框與文字區的內容、contenteditable，以及標了 data-no-convert 或
 * translate="no" 的元素（書名、章節名、原文日文等使用者內容）。
 */

export type UiLanguage = 'zh-TW' | 'zh-CN'

export const UI_LANGUAGES: ReadonlyArray<{ code: UiLanguage; label: string }> = [
  { code: 'zh-TW', label: '繁體中文（台灣）' },
  { code: 'zh-CN', label: '简体中文' },
]

const STORAGE_KEY = 'saber.uiLanguage'
const DEFAULT_LANGUAGE: UiLanguage = 'zh-TW'
const CONVERTED_ATTRIBUTES = ['placeholder', 'title', 'aria-label', 'alt', 'aria-description']
const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'INPUT', 'CODE', 'PRE', 'NOSCRIPT'])
const OPT_OUT_SELECTOR = '[data-no-convert], [translate="no"], [contenteditable=""], [contenteditable="true"]'
const HAN = /[㐀-鿿]/

// OpenCC 只換字、沒換到的大陸介面用語，轉換後再換成台灣說法（桌面 ui_language.py 有同一份）
export const TW_UI_TERMS: ReadonlyArray<readonly [string, string]> = [
  ["(?<!重)新建", "新增"],
  ["居中", "置中"],
  ["文本", "文字"],
  ["配置", "設定"],
  ["教程", "教學"],
  ["當前", "目前"],
  ["撤銷", "復原"],
  ["賬號", "帳號"],
  ["賬戶", "帳戶"],
  ["質量", "品質"],
  ["模板", "範本"],
  ["影象", "影像"],
  ["畫素", "像素"],
  ["反饋", "回饋"],
  ["(?<![接線])埠", "連接埠"],
]
const TW_UI_TERM_PATTERNS = TW_UI_TERMS.map(([pattern, replacement]) => [new RegExp(pattern, 'g'), replacement] as const)

let convert: ((text: string) => string) | null = null
let observer: MutationObserver | null = null
const cache = new Map<string, string>()

function isLanguage(value: unknown): value is UiLanguage {
  return value === 'zh-TW' || value === 'zh-CN'
}

/** 目前介面語言：網址 ?lang= 優先（控制中心開啟網頁時會帶），其次是上次的選擇。 */
export function currentUiLanguage(): UiLanguage {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get('lang')
    if (isLanguage(fromUrl)) return fromUrl
  } catch {
    // 沒有網址參數時用儲存的選擇
  }
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (isLanguage(stored)) return stored
  } catch {
    // 無法讀取儲存空間時用預設語言
  }
  return DEFAULT_LANGUAGE
}

function rememberLanguage(language: UiLanguage): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, language)
  } catch {
    // 無法儲存時只影響下次開啟的預設語言
  }
}

/** 切換介面語言並重新載入頁面（简体中文需要原文，重新載入最可靠）。 */
export function setUiLanguage(language: UiLanguage): void {
  rememberLanguage(language)
  const url = new URL(window.location.href)
  url.searchParams.delete('lang')
  window.location.replace(url.toString())
}

export function convertUiText(text: string): string {
  if (!convert || !HAN.test(text)) return text
  const cached = cache.get(text)
  if (cached !== undefined) return cached
  let converted = convert(text)
  for (const [pattern, replacement] of TW_UI_TERM_PATTERNS) converted = converted.replace(pattern, replacement)
  if (cache.size > 20000) cache.clear()
  cache.set(text, converted)
  return converted
}

function excluded(element: Element | null): boolean {
  if (!element) return true
  if (SKIP_TAGS.has(element.tagName)) return true
  return element.closest(OPT_OUT_SELECTOR) !== null
}

function convertTextNode(node: Text): void {
  const value = node.data
  if (!HAN.test(value) || excluded(node.parentElement)) return
  const converted = convertUiText(value)
  if (converted !== value) node.data = converted
}

function convertAttributes(element: Element): void {
  if (excluded(element) && !SKIP_TAGS.has(element.tagName)) return
  if (element.closest('[data-no-convert], [translate="no"]')) return
  for (const name of CONVERTED_ATTRIBUTES) {
    const value = element.getAttribute(name)
    if (value && HAN.test(value)) {
      const converted = convertUiText(value)
      if (converted !== value) element.setAttribute(name, converted)
    }
  }
}

function convertTree(root: Node): void {
  if (root.nodeType === Node.TEXT_NODE) {
    convertTextNode(root as Text)
    return
  }
  if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_NODE) return
  if (root.nodeType === Node.ELEMENT_NODE) {
    const element = root as Element
    if (element.closest('[data-no-convert], [translate="no"]')) return
    convertAttributes(element)
  }
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (node.nodeType === Node.ELEMENT_NODE) {
        const element = node as Element
        if (element.hasAttribute('data-no-convert') || element.getAttribute('translate') === 'no') {
          return NodeFilter.FILTER_REJECT
        }
      }
      return NodeFilter.FILTER_ACCEPT
    },
  })
  let node = walker.nextNode()
  while (node) {
    if (node.nodeType === Node.TEXT_NODE) convertTextNode(node as Text)
    else convertAttributes(node as Element)
    node = walker.nextNode()
  }
}

function patchNativeDialogs(): void {
  const { alert, confirm, prompt } = window
  window.alert = (message?: unknown) => alert.call(window, typeof message === 'string' ? convertUiText(message) : message)
  window.confirm = (message?: string) => confirm.call(window, typeof message === 'string' ? convertUiText(message) : message)
  window.prompt = (message?: string, value?: string) => prompt.call(
    window,
    typeof message === 'string' ? convertUiText(message) : message,
    value,
  )
}

/**
 * 在掛載 Vue 之前呼叫。zh-TW 時載入轉換字典並開始監看畫面；zh-CN 什麼都不做。
 * 載入失敗時照常顯示原文，不影響使用。
 */
/** 停止轉換（測試用）。 */
export function stopUiLanguage(): void {
  observer?.disconnect()
  observer = null
  convert = null
  cache.clear()
}

export async function startUiLanguage(): Promise<UiLanguage> {
  const language = currentUiLanguage()
  rememberLanguage(language)
  document.documentElement.lang = language
  if (language !== 'zh-TW') return language
  try {
    const OpenCC = await import('opencc-js/cn2t')
    convert = OpenCC.Converter({ from: 'cn', to: 'twp' })
  } catch (error) {
    console.warn('無法載入繁體中文轉換，介面以原文顯示', error)
    return language
  }
  convertTree(document)
  document.title = convertUiText(document.title)
  observer?.disconnect()
  observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === 'characterData') {
        convertTextNode(mutation.target as Text)
      } else if (mutation.type === 'attributes') {
        convertAttributes(mutation.target as Element)
      } else {
        mutation.addedNodes.forEach(convertTree)
      }
    }
  })
  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: CONVERTED_ATTRIBUTES,
  })
  patchNativeDialogs()
  return language
}
