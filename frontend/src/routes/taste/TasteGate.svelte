<script lang="ts">
	import { Button } from '#lib/components/ui/button/index.js'
	import { loadTaste, taste } from '#lib/taste.svelte.js'
	import { goto } from '$app/navigation'
	import { page } from '$app/state'
	import { onMount, type Snippet } from 'svelte'

	const TASTE_PATH = '/taste'

	let { children }: { children: Snippet } = $props()

	const isTastePage = $derived(page.url.pathname === TASTE_PATH)

	$effect(() => {
		// Every page needs a taste, so check once here. replaceState keeps Back from returning to a gated page.
		if (taste.status === 'none' && !isTastePage)
			void goto(TASTE_PATH, { replaceState: true })
	})

	onMount(loadTaste)
</script>

{#if isTastePage || taste.status === 'ready'}
	{@render children()}
{:else if taste.status === 'error'}
	<div class="flex flex-col items-center gap-3 px-6 py-12 text-center">
		<p class="text-muted-foreground">{taste.error}</p>
		<Button type="button" variant="outline" onclick={loadTaste}>Retry</Button>
	</div>
{/if}
