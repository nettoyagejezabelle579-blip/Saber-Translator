import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { showToast } from './utils/toast'
import { startUiLanguage } from './i18n/uiLanguage'

import './styles/tokens/foundation.css'
import './styles/tokens/semantic.css'
import './styles/tokens/component.css'
import './styles/tokens/domain.css'
import './styles/reset.css'

const app = createApp(App)

const pinia = createPinia()
app.use(pinia)

app.use(router)

app.config.errorHandler = (err, _instance, info) => {
  const message = err instanceof Error ? err.message : String(err)
  showToast(`应用运行出错：${message || info}`, 'error', 5000)
}

// 先載入介面語言（預設繁體中文），再顯示畫面，避免先閃過简体
void startUiLanguage().finally(() => app.mount('#app'))
