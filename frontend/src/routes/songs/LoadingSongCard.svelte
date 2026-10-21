<script lang="ts">
	import LoaderCircleIcon from '@lucide/svelte/icons/loader-circle'

	let {
		title,
		artist,
		thumbnailUrl,
		albumArtUrl,
	}: {
		title: string
		artist: string
		thumbnailUrl?: string
		albumArtUrl?: string | null
	} = $props()

	let failedUrls: string[] = $state([])
	let loadedUrl: string | null = $state(null)
	// Same order as SongCard: album art, then the YouTube thumbnail.
	let imageUrl = $derived(
		[albumArtUrl, thumbnailUrl].find(
			(url): url is string => !!url && !failedUrls.includes(url)
		)
	)
	let isThumbnail = $derived(imageUrl !== undefined && imageUrl !== albumArtUrl)
	let isImageLoaded = $derived(imageUrl !== undefined && loadedUrl === imageUrl)
</script>

<article class="w-full" aria-busy="true" aria-label="Analyzing {title}">
	<div
		class="relative flex aspect-square items-center justify-center overflow-hidden rounded-lg bg-muted"
	>
		{#if imageUrl}
			{#key imageUrl}
				<img
					src={imageUrl}
					alt=""
					class="absolute inset-0 size-full object-cover transition-opacity duration-500 motion-reduce:transition-none {isThumbnail
						? 'scale-[1.334]'
						: ''} {isImageLoaded ? 'opacity-40' : 'opacity-0'}"
					onload={() => (loadedUrl = imageUrl ?? null)}
					onerror={() => (failedUrls = [...failedUrls, imageUrl])}
				/>
			{/key}
		{/if}
		<LoaderCircleIcon
			class="relative size-8 animate-spin text-muted-foreground motion-reduce:animate-none"
			aria-hidden="true"
		/>
	</div>
	<div class="mt-2 min-w-0 opacity-60">
		<p class="truncate text-sm font-medium" {title}>{title}</p>
		<p class="truncate text-sm text-muted-foreground">{artist}</p>
	</div>
</article>
