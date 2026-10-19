<script lang="ts">
	import type { Song } from '#lib/api.js'
	import { Badge } from '#lib/components/ui/badge/index.js'
	import { player, playSong, togglePlayback } from '#lib/player.svelte.js'
	import MusicIcon from '@lucide/svelte/icons/music'
	import PauseIcon from '@lucide/svelte/icons/pause'
	import PlayIcon from '@lucide/svelte/icons/play'

	let { song, queue, origin }: { song: Song; queue?: Song[]; origin?: string } =
		$props()

	let confidence = $derived(`${Math.round(song.confidence * 100)}%`)
	let isCurrent = $derived(player.current?.video_id === song.video_id)
	let isPlaying = $derived(isCurrent && player.status === 'playing')

	function handlePlay() {
		if (isCurrent) togglePlayback()
		else playSong(song, queue, origin)
	}
</script>

<article
	class="group relative w-full"
	aria-label="{song.title} by {song.artist}"
>
	<div
		class="relative flex aspect-square items-center justify-center overflow-hidden rounded-lg bg-muted ring-2 {isCurrent
			? 'ring-primary'
			: 'ring-transparent'}"
	>
		<MusicIcon class="size-10 text-muted-foreground" aria-hidden="true" />
		<button
			type="button"
			class="absolute inset-0 flex cursor-pointer items-center justify-center bg-black/40 opacity-0 outline-none group-hover:opacity-100 focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-ring {isCurrent
				? 'opacity-100'
				: ''}"
			aria-label="{isPlaying ? 'Pause' : 'Play'} {song.title}"
			onclick={handlePlay}
		>
			{#if isPlaying}
				<PauseIcon class="size-10 text-white" aria-hidden="true" />
			{:else}
				<PlayIcon class="size-10 text-white" aria-hidden="true" />
			{/if}
		</button>
		<Badge class="absolute bottom-2 left-2" variant="secondary"
			>{confidence}</Badge
		>
	</div>
	<div class="mt-2 min-w-0">
		<p class="truncate text-sm font-medium" title={song.title}>{song.title}</p>
		<p class="truncate text-sm text-muted-foreground">{song.artist}</p>
		{#if song.album}
			<p class="truncate text-xs text-muted-foreground/70">{song.album}</p>
		{/if}
	</div>
</article>
