<script lang="ts">
	import type { Song } from '#lib/api.js'
	import { Badge } from '#lib/components/ui/badge/index.js'
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link'
	import MusicIcon from '@lucide/svelte/icons/music'

	let { song }: { song: Song } = $props()

	let confidence = $derived(`${Math.round(song.confidence * 100)}%`)
</script>

<article
	class="group relative w-full"
	aria-label="{song.title} by {song.artist}"
>
	<div
		class="relative flex aspect-square items-center justify-center overflow-hidden rounded-lg bg-muted"
	>
		<MusicIcon class="size-10 text-muted-foreground" aria-hidden="true" />
		<Badge class="absolute bottom-2 left-2" variant="secondary"
			>{confidence}</Badge
		>
		<a
			class="absolute top-2 right-2 rounded-md bg-background/70 p-1.5 outline-none hover:bg-background focus-visible:ring-2 focus-visible:ring-ring"
			href={song.url}
			target="_blank"
			rel="noopener noreferrer"
			aria-label="Open {song.title} on YouTube"
		>
			<ExternalLinkIcon class="size-4" aria-hidden="true" />
		</a>
	</div>
	<div class="mt-2 min-w-0">
		<p class="truncate text-sm font-medium" title={song.title}>{song.title}</p>
		<p class="truncate text-sm text-muted-foreground">{song.artist}</p>
		{#if song.album}
			<p class="truncate text-xs text-muted-foreground/70">{song.album}</p>
		{/if}
	</div>
</article>
