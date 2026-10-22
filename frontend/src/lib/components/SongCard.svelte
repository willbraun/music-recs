<script lang="ts">
	import type { Song } from '#lib/api.js'
	import AppleIcon from '#lib/components/icons/Apple.svelte'
	import SpotifyIcon from '#lib/components/icons/Spotify.svelte'
	import YouTubeIcon from '#lib/components/icons/YouTube.svelte'
	import { Badge } from '#lib/components/ui/badge/index.js'
	import { Skeleton } from '#lib/components/ui/skeleton/index.js'
	import {
		buildAppleMusicSearchUrl,
		buildSpotifySearchUrl,
	} from '#lib/links.js'
	import { player, playSong, togglePlayback } from '#lib/player.svelte.js'
	import MusicIcon from '@lucide/svelte/icons/music'
	import PauseIcon from '@lucide/svelte/icons/pause'
	import PlayIcon from '@lucide/svelte/icons/play'

	let {
		song,
		queue,
		origin,
		eager = false,
	}: { song: Song; queue?: Song[]; origin?: string; eager?: boolean } = $props()

	// hqdefault is 4:3 with black bars around a centered square cover; 4/3 zoom crops the bars.
	const THUMBNAIL_ZOOM = 'scale-[1.334]'

	let failedUrls: string[] = $state([])
	let loadedUrl: string | null = $state(null)
	// Album art first, then the YouTube thumbnail; a source that failed to load is not retried.
	let imageUrl = $derived(
		[song.album_art_url, song.thumbnail_url].find(
			(url): url is string => !!url && !failedUrls.includes(url)
		)
	)
	let isThumbnail = $derived(
		imageUrl !== undefined && imageUrl !== song.album_art_url
	)
	let isImageLoaded = $derived(imageUrl !== undefined && loadedUrl === imageUrl)
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
		{#if imageUrl}
			{#if !isImageLoaded}
				<Skeleton class="absolute inset-0 rounded-none" />
			{/if}
			<!-- Keyed so a fallback source starts with a fresh element. -->
			{#key imageUrl}
				<img
					src={imageUrl}
					alt=""
					loading={eager ? 'eager' : 'lazy'}
					class="absolute inset-0 size-full object-cover transition-opacity duration-300 motion-reduce:transition-none {isThumbnail
						? THUMBNAIL_ZOOM
						: ''} {isImageLoaded ? 'opacity-100' : 'opacity-0'}"
					onload={() => (loadedUrl = imageUrl ?? null)}
					onerror={() => imageUrl && failedUrls.push(imageUrl)}
				/>
			{/key}
		{:else}
			<MusicIcon class="size-10 text-muted-foreground" aria-hidden="true" />
		{/if}
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
		<div
			class="absolute top-2 right-2 flex gap-1 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100"
		>
			<a
				class="flex size-8 items-center justify-center rounded-md bg-black/60 text-white outline-none focus-visible:ring-2 focus-visible:ring-ring"
				href={song.url}
				target="_blank"
				rel="noopener noreferrer"
				aria-label="Open {song.title} on YouTube"
				title="Open on YouTube"
			>
				<YouTubeIcon class="size-5" />
			</a>
			<a
				class="flex size-8 items-center justify-center rounded-md bg-black/60 text-white outline-none focus-visible:ring-2 focus-visible:ring-ring"
				href={buildAppleMusicSearchUrl(song)}
				target="_blank"
				rel="noopener noreferrer"
				aria-label="Open {song.title} on Apple Music"
				title="Open on Apple Music"
			>
				<AppleIcon class="size-5" />
			</a>
			<a
				class="flex size-8 items-center justify-center rounded-md bg-black/60 text-white outline-none focus-visible:ring-2 focus-visible:ring-ring"
				href={buildSpotifySearchUrl(song)}
				target="_blank"
				rel="noopener noreferrer"
				aria-label="Open {song.title} on Spotify"
				title="Open on Spotify"
			>
				<SpotifyIcon class="size-5" />
			</a>
		</div>
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
