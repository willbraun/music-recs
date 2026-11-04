<script lang="ts">
	import { Button } from '#lib/components/ui/button/index.js'
	import { loadTaste, taste } from '#lib/taste.svelte.js'
	import { goto } from '$app/navigation'
	import { page } from '$app/state'
	import { onMount, type Snippet } from 'svelte'

	const TASTE_PATH = '/taste'
	// Pages that work without a taste: the taste page itself and the static ones.
	const UNGATED_PATHS = [TASTE_PATH, '/models', '/about']

	let { children }: { children: Snippet } = $props()

	const isUngated = $derived(UNGATED_PATHS.includes(page.url.pathname))

	$effect(() => {
		// Other pages need a taste, so check once here. replaceState keeps Back from returning to a gated page.
		if (taste.status === 'none' && !isUngated)
			void goto(TASTE_PATH, { replaceState: true })
	})

	onMount(loadTaste)
</script>

{#if isUngated || taste.status === 'ready'}
	{@render children()}
{:else if taste.status === 'error'}
	<div class="flex flex-col items-center gap-3 px-6 py-12 text-center">
		<p class="text-muted-foreground">{taste.error}</p>
		<Button type="button" variant="outline" onclick={loadTaste}>Retry</Button>
	</div>
{/if}
