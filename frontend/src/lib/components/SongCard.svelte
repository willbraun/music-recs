<script lang="ts">
	import type { Song } from '#lib/api.js'
	import { Badge } from '#lib/components/ui/badge/index.js'
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link'
	import MusicIcon from '@lucide/svelte/icons/music'

	let { song }: { song: Song } = $props()

	let confidence = $derived(`${Math.round(song.confidence * 100)}%`)
</script>

<article class="group relative w-full" aria-label="{song.title} by {song.artist}">
	<div class="bg-muted relative flex aspect-square items-center justify-center overflow-hidden rounded-lg">
		<MusicIcon class="text-muted-foreground size-10" aria-hidden="true" />
		<Badge class="absolute bottom-2 left-2" variant="secondary">{confidence}</Badge>
		<a
			class="bg-background/70 hover:bg-background focus-visible:ring-ring absolute top-2 right-2 rounded-md p-1.5 outline-none focus-visible:ring-2"
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
		<p class="text-muted-foreground truncate text-sm">{song.artist}</p>
		{#if song.album}
			<p class="text-muted-foreground/70 truncate text-xs">{song.album}</p>
		{/if}
	</div>
</article>
