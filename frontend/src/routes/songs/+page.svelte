<script lang="ts">
	import { listSongs, type Song } from '#lib/api.js'
	import SongRow from '#lib/components/SongRow.svelte'
	import { Button } from '#lib/components/ui/button/index.js'
	import { playSong } from '#lib/player.svelte.js'
	import { onMount } from 'svelte'

	const SONGS_QUEUE_ORIGIN = 'songs'
	const REVEAL_CLASS =
		'animate-in fade-in slide-in-from-bottom-4 fill-mode-backwards duration-500 motion-reduce:animate-none'
	const STAGGER_MS = 10
	// Caps the delay so long lists don't keep the last rows waiting.
	const MAX_DELAY_MS = 1000

	let songs: Song[] = $state([])
	let isLoading = $state(true)
	let errorMessage: string | null = $state(null)

	async function loadSongs() {
		isLoading = true
		errorMessage = null
		try {
			songs = await listSongs()
		} catch (error) {
			errorMessage =
				error instanceof Error ? error.message : 'Could not load songs'
		} finally {
			isLoading = false
		}
	}

	function playFromList(song: Song) {
		playSong(song, songs, SONGS_QUEUE_ORIGIN)
	}

	onMount(loadSongs)
</script>

<svelte:head>
	<title>Songs</title>
</svelte:head>

<main class="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-8">
	<div class="flex items-baseline justify-between">
		<h1 class="text-3xl font-semibold tracking-tight">Songs</h1>
		{#if !isLoading && !errorMessage}
			<p class="text-muted-foreground">
				{songs.length}
				{songs.length === 1 ? 'song' : 'songs'}
			</p>
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
		<div
			class="hidden grid-cols-[3rem_2fr_1.5fr_1.5fr_4rem] gap-4 px-3 text-xs font-medium text-muted-foreground uppercase md:grid"
			aria-hidden="true"
		>
			<span></span>
			<span>Title</span>
			<span>Artist</span>
			<span>Album</span>
			<span class="text-right">Match</span>
		</div>
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
