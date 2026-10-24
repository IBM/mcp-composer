import DefaultTheme from 'vitepress/theme'
import Cookbook from './Cookbook.vue'
import './custom.css'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('Cookbook', Cookbook)
  },
}
