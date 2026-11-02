<script setup lang="ts">
import { computed, ref } from 'vue'
import { withBase } from 'vitepress'
import recipes from '../../cookbook/catalog.json'

const topic = ref('all')
const query = ref('')

const topics = computed(() => {
  const seen: string[] = []
  for (const recipe of recipes) {
    if (!seen.includes(recipe.topic)) seen.push(recipe.topic)
  }
  return seen
})

const visible = computed(() => {
  const q = query.value.trim().toLowerCase()
  return recipes.filter((recipe) => {
    if (topic.value !== 'all' && recipe.topic !== topic.value) return false
    if (!q) return true
    return `${recipe.title} ${recipe.summary} ${recipe.topic}`.toLowerCase().includes(q)
  })
})

function count(name: string) {
  return recipes.filter((recipe) => recipe.topic === name).length
}
</script>

<template>
  <div class="cb">
    <header class="cb-hero">
      <p class="cb-kicker">MCP Composer</p>
      <h1>Cookbook</h1>
      <p>
        Short tasks you can run. Each card opens a page. The page points at a program under
        <code>example/cookbook</code>.
      </p>
    </header>

    <div class="cb-controls">
      <input v-model="query" type="search" placeholder="Search recipes" aria-label="Search recipes" />
      <div class="cb-chips" role="group" aria-label="Topic">
        <button type="button" :class="{ on: topic === 'all' }" @click="topic = 'all'">
          All <span>{{ recipes.length }}</span>
        </button>
        <button
          v-for="name in topics"
          :key="name"
          type="button"
          :class="{ on: topic === name }"
          @click="topic = name"
        >
          {{ name }} <span>{{ count(name) }}</span>
        </button>
      </div>
    </div>

    <div class="cb-grid">
      <a
        v-for="recipe in visible"
        :key="recipe.slug"
        class="cb-card"
        :href="withBase(`/cookbook/${recipe.slug}`)"
      >
        <p class="cb-topic">{{ recipe.topic }}</p>
        <h2>{{ recipe.title }}</h2>
        <p>{{ recipe.summary }}</p>
      </a>
    </div>
    <p v-if="!visible.length" class="cb-empty">No recipe matches that search.</p>
  </div>
</template>

<style scoped>
.cb { max-width: 1080px; margin: 0 auto; padding: 56px 24px 96px; }
.cb-kicker {
  margin: 0 0 8px;
  font-size: 13px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--vp-c-brand-1);
  font-weight: 650;
}
.cb-hero h1 { margin: 0 0 12px; font-size: 44px; line-height: 1.1; font-weight: 640; }
.cb-hero p { margin: 0; max-width: 640px; font-size: 18px; line-height: 1.5; color: var(--vp-c-text-2); }
.cb-controls { margin-top: 36px; display: flex; flex-direction: column; gap: 14px; }
.cb-controls input[type='search'] {
  width: 100%;
  padding: 12px 14px;
  font-size: 16px;
  border: 1px solid var(--vp-c-divider);
  border-radius: 10px;
  background: var(--vp-c-bg);
  color: var(--vp-c-text-1);
}
.cb-controls input[type='search']:focus { outline: 2px solid var(--vp-c-brand-1); border-color: transparent; }
.cb-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.cb-chips button {
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid var(--vp-c-divider);
  background: var(--vp-c-bg);
  color: var(--vp-c-text-1);
  font-size: 14px;
}
.cb-chips button span { margin-left: 4px; color: var(--vp-c-text-3); }
.cb-chips button.on { background: var(--vp-c-brand-1); border-color: var(--vp-c-brand-1); color: white; }
.cb-chips button.on span { color: rgba(255, 255, 255, 0.82); }
.cb-grid { margin-top: 28px; display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.cb-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 20px;
  border: 1px solid var(--vp-c-divider);
  border-radius: 14px;
  background: var(--vp-c-bg-soft);
  color: inherit;
  text-decoration: none;
}
.cb-card:hover { border-color: var(--vp-c-brand-1); }
.cb-topic { margin: 0; font-size: 12px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--vp-c-brand-1); font-weight: 650; }
.cb-card h2 { margin: 0; font-size: 18px; line-height: 1.35; font-weight: 630; }
.cb-card p { margin: 0; color: var(--vp-c-text-2); font-size: 14px; line-height: 1.5; }
.cb-empty { margin-top: 28px; color: var(--vp-c-text-2); }
</style>
