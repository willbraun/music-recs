<script lang="ts">
	import { listSongs, type Song } from '#lib/api.js'
	import { Button } from '#lib/components/ui/button/index.js'
	import { playSong } from '#lib/player.svelte.js'
	import ChevronLeftIcon from '@lucide/svelte/icons/chevron-left'
	import ChevronRightIcon from '@lucide/svelte/icons/chevron-right'
	import { onMount } from 'svelte'
	import SongRow from './SongRow.svelte'

	const SONGS_QUEUE_ORIGIN = 'songs'
	const REVEAL_CLASS =
		'animate-in fade-in slide-in-from-bottom-4 fill-mode-backwards duration-500 motion-reduce:animate-none'
	const STAGGER_MS = 10
	// Caps the delay so long lists don't keep the last rows waiting.
	const MAX_DELAY_MS = 1000

	let songs: Song[] = $state([])
	let total = $state(0)
	let pageNumber = $state(1)
	let pageSize = $state(50)
	let isLoading = $state(true)
	let errorMessage: string | null = $state(null)

	const lastPage = $derived(Math.max(1, Math.ceil(total / pageSize)))
	const rangeStart = $derived((pageNumber - 1) * pageSize + 1)
	const rangeEnd = $derived(rangeStart + songs.length - 1)

	async function loadSongs() {
		isLoading = true
		errorMessage = null
		try {
			const result = await listSongs(pageNumber)
			pageSize = result.page_size
			total = result.total
			songs = result.items
			// The page is past the end, e.g. after songs were removed.
			if (songs.length === 0 && total > 0 && pageNumber > lastPage) {
				pageNumber = lastPage
				return loadSongs()
			}
		} catch (error) {
			errorMessage =
				error instanceof Error ? error.message : 'Could not load songs'
		} finally {
			isLoading = false
		}
	}

	function goToPage(target: number) {
		pageNumber = target
		window.scrollTo({ top: 0 })
		loadSongs()
	}

	function playFromList(song: Song) {
		playSong(song, songs, SONGS_QUEUE_ORIGIN)
	}

	onMount(loadSongs)
</script>

<svelte:head>
	<title>Songs</title>
</svelte:head>

<main class="mx-auto flex max-w-7xl flex-col gap-3 px-6 pt-8 pb-8">
	<div
		class="sticky top-12.25 z-30 -mx-6 flex flex-col gap-4 border-b bg-background/80 px-6 py-3 backdrop-blur"
	>
		<div class="flex items-center justify-between gap-4">
			<h1 class="text-3xl font-semibold tracking-tight">Songs</h1>
			<div class="flex items-center gap-3">
				{#if !isLoading && !errorMessage && songs.length > 0}
					<p class="text-sm text-muted-foreground tabular-nums">
						{rangeStart}-{rangeEnd} of {total}
					</p>
				{/if}
				{#if total > pageSize}
					<div class="flex items-center gap-1">
						<Button
							type="button"
							variant="outline"
							size="icon-sm"
							aria-label="Previous page"
							disabled={isLoading || pageNumber <= 1}
							onclick={() => goToPage(pageNumber - 1)}
						>
							<ChevronLeftIcon />
						</Button>
						<Button
							type="button"
							variant="outline"
							size="icon-sm"
							aria-label="Next page"
							disabled={isLoading || pageNumber >= lastPage}
							onclick={() => goToPage(pageNumber + 1)}
						>
							<ChevronRightIcon />
						</Button>
					</div>
				{/if}
			</div>
		</div>

		{#if !isLoading && !errorMessage && songs.length > 0}
			<div
				class="hidden grid-cols-[3rem_2fr_1.5fr_1.5fr_4rem_1.3rem] gap-4 px-3 text-xs font-medium text-muted-foreground uppercase md:grid"
				aria-hidden="true"
			>
				<span></span>
				<span>Title</span>
				<span>Artist</span>
				<span>Album</span>
				<span>Match</span>
			</div>
		{/if}
	</div>

	{#if isLoading}
		<div aria-busy="true" aria-label="Loading songs"></div>
	{:else if errorMessage}
		<div class="flex flex-col items-center gap-3 py-12 text-center">
			<p class="text-muted-foreground">{errorMessage}</p>
			<Button type="button" variant="outline" onclick={loadSongs}>Retry</Button>
		</div>
	{:else if songs.length === 0}
		<p class="py-12 text-center text-muted-foreground">
			No songs yet. Find some on the <a href="/" class="underline">Home page</a
			>.
		</p>
	{:else}
		<ul class="flex flex-col">
			{#each songs as song, index (song.video_id)}
				<li
					class={REVEAL_CLASS}
					style:animation-delay="{Math.min(index * STAGGER_MS, MAX_DELAY_MS)}ms"
				>
					<SongRow {song} onplay={playFromList} />
				</li>
			{/each}
		</ul>
	{/if}
</main>
