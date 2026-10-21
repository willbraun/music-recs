<script lang="ts">
	import type { Song } from '#lib/api.js'
	import { player } from '#lib/player.svelte.js'
	import MusicIcon from '@lucide/svelte/icons/music'

	let { song, onplay }: { song: Song; onplay: (song: Song) => void } = $props()

	// hqdefault is 4:3 with black bars around a centered square cover; 4/3 zoom crops the bars.
	const THUMBNAIL_ZOOM = 'scale-[1.334]'

	let failedUrls: string[] = $state([])
	let loadedUrl: string | null = $state(null)
	let imageUrl = $derived(
		[song.album_art_url, song.thumbnail_url].find(
			(url): url is string => !!url && !failedUrls.includes(url)
		)
	)
	let isThumbnail = $derived(
		imageUrl !== undefined && imageUrl !== song.album_art_url
	)
	// Confidence is the probability of the model's answer, so a NO flips it into the chance of YES.
	let matchScore = $derived(
		`${Math.round((song.recommended ? song.confidence : 1 - song.confidence) * 100)}%`
	)
	let isCurrent = $derived(player.current?.video_id === song.video_id)
</script>

<button
	type="button"
	class="grid w-full cursor-pointer grid-cols-[3rem_1fr_auto] items-center gap-4 rounded-lg px-3 py-2 text-left outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring md:grid-cols-[3rem_2fr_1.5fr_1.5fr_4rem] {isCurrent
		? 'bg-muted'
		: ''}"
	aria-label="Play {song.title} by {song.artist}"
	aria-current={isCurrent || undefined}
	onclick={() => onplay(song)}
>
	<span
		class="relative flex size-12 items-center justify-center overflow-hidden rounded-md {imageUrl
			? ''
			: 'bg-muted'}"
	>
		{#if imageUrl}
			{#key imageUrl}
				<img
					src={imageUrl}
					alt=""
					loading="lazy"
					class="absolute inset-0 size-full object-cover transition-opacity duration-300 motion-reduce:transition-none {isThumbnail
						? THUMBNAIL_ZOOM
						: ''} {loadedUrl === imageUrl ? 'opacity-100' : 'opacity-0'}"
					onload={() => (loadedUrl = imageUrl ?? null)}
					onerror={() => imageUrl && failedUrls.push(imageUrl)}
				/>
			{/key}
		{:else}
			<MusicIcon class="size-5 text-muted-foreground" aria-hidden="true" />
		{/if}
	</span>
	<span class="min-w-0">
		<span class="block text-sm font-medium break-all" title={song.title}
			>{song.title}</span
		>
		<span class="block text-sm break-all text-muted-foreground md:hidden"
			>{song.artist}</span
		>
	</span>
	<span class="hidden text-sm break-all text-muted-foreground md:block"
		>{song.artist}</span
	>
	<span class="hidden text-sm break-all text-muted-foreground md:block"
		>{song.album ?? ''}</span
	>
	<span
		class="text-right text-sm font-medium tabular-nums {song.recommended
			? 'text-green-500'
			: 'text-red-500'}"
		title={song.recommended ? 'Recommended' : 'Not recommended'}
		>{matchScore}<span class="sr-only"
			>, {song.recommended ? 'recommended' : 'not recommended'}</span
		></span
	>
</button>
