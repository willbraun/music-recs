<script lang="ts">
	import { Button, buttonVariants } from '#lib/components/ui/button/index.js'
	import * as Popover from '#lib/components/ui/popover/index.js'
	import { Skeleton } from '#lib/components/ui/skeleton/index.js'
	import { Slider } from '#lib/components/ui/slider/index.js'
	import {
		areModelsDownloaded,
		getActiveDownloads,
		modelCache,
		watchModelCache,
	} from '#lib/modelCache.svelte.js'
	import { playSong } from '#lib/player.svelte.js'
	import {
		run,
		RUN_QUEUE_ORIGIN,
		startNewRun,
		type RunCard,
	} from '#lib/run.svelte.js'
	import { loadTaste, taste } from '#lib/taste.svelte.js'
	import MinusIcon from '@lucide/svelte/icons/minus'
	import MusicIcon from '@lucide/svelte/icons/music'
	import PlayIcon from '@lucide/svelte/icons/play'
	import PlusIcon from '@lucide/svelte/icons/plus'
	import SettingsIcon from '@lucide/svelte/icons/settings'
	import SparklesIcon from '@lucide/svelte/icons/sparkles'
	import { onMount } from 'svelte'
	import LoadingSongCard from '../lib/components/LoadingSongCard.svelte'
	import ModelDownload from '../lib/components/ModelDownload.svelte'
	import SongCard from '../lib/components/SongCard.svelte'
	import TasteModal from './TasteModal.svelte'

	const MIN_COUNT = 1
	const MAX_COUNT = 50
	const REVEAL_CLASS =
		'animate-in fade-in slide-in-from-bottom-4 duration-500 motion-reduce:animate-none'

	let count = $state(3)
	let exploration = $state(50)
	let isTasteModalOpen = $state(false)
	// Set when Discover opens with no taste and no models, to follow the first-run flow until the first run.
	let isFirstRun = $state(false)

	let isRunActive = $derived(
		run.phase === 'preparing' || run.phase === 'streaming'
	)
	let hasRecommendations = $derived(
		run.cards.some((card) => card.kind === 'song')
	)
	let isGridVisible = $derived(run.phase !== 'idle' && run.cards.length > 0)
	let isEmpty = $derived(run.phase === 'done' && !hasRecommendations)
	let songs = $derived(
		run.cards.flatMap((card) => (card.kind === 'song' ? [card.song] : []))
	)
	// A download can come from this run or from the Models page.
	let downloads = $derived(getActiveDownloads())
	let isDownloading = $derived(downloads.length > 0)
	let firstRunNotice = $derived.by(() => {
		if (!isFirstRun) return ''
		if (isDownloading)
			return 'Your taste is saved. Models are still downloading...'
		return areModelsDownloaded() ? 'Your taste is ready.' : ''
	})

	let isPlayVisible = $derived(songs.length > 0)

	// Content that survived navigation is shown as-is; only new content animates.
	const restoredKeys = new Set(run.cards.map(getCardKey))
	const wasGridVisible = run.phase !== 'idle' && run.cards.length > 0
	const wasDownloadsVisible = getActiveDownloads().length > 0
	const gridRevealClass = wasGridVisible ? '' : REVEAL_CLASS

	onMount(watchModelCache)

	$effect(() => {
		if (
			taste.status === 'none' &&
			modelCache.status === 'ready' &&
			!areModelsDownloaded()
		)
			isFirstRun = true
	})

	function getCardRevealClass(card: RunCard): string {
		return restoredKeys.has(getCardKey(card)) ? '' : REVEAL_CLASS
	}

	function getCardKey(card: RunCard): string {
		return card.kind === 'loading' ? card.video_id : card.song.video_id
	}

	function playAll() {
		playSong(songs[0], songs, RUN_QUEUE_ORIGIN)
	}

	function submitRun(event: SubmitEvent) {
		event.preventDefault()
		if (isRunActive || isDownloading) return
		isFirstRun = false
		void startNewRun(count, exploration)
	}
</script>

<svelte:head>
	<title>Discover something new</title>
</svelte:head>

<main class="mx-auto flex max-w-7xl flex-col gap-10 px-6 py-12">
	<section class="flex flex-col items-center gap-6 text-center">
		<div class="flex flex-col gap-2">
			<h1 class="text-3xl font-semibold tracking-tight">
				Discover something new
			</h1>
			<p class="text-muted-foreground">
				Based on your taste, I'll find music you might like
			</p>
		</div>

		{#if taste.status === 'loading'}
			<Skeleton class="h-11 w-44" aria-label="Loading taste" />
		{:else if taste.status === 'error'}
			<div class="flex flex-col items-center gap-3">
				<p class="text-muted-foreground">{taste.error}</p>
				<Button type="button" variant="outline" onclick={loadTaste}
					>Retry</Button
				>
			</div>
		{:else if taste.status === 'none'}
			<Button type="button" size="lg" onclick={() => (isTasteModalOpen = true)}>
				<MusicIcon />
				What music do you like?
			</Button>
		{:else}
			<form class="relative flex items-center gap-2" onsubmit={submitRun}>
				<Button type="submit" size="lg" disabled={isRunActive || isDownloading}>
					<SparklesIcon />
					{#if isRunActive}Finding music...{:else if isDownloading}Getting
						ready...{:else}Find new music{/if}
				</Button>

				<Popover.Root>
					<Popover.Trigger
						type="button"
						class={`${buttonVariants({ variant: 'outline', size: 'icon-lg' })} absolute -right-12`}
						aria-label="Settings"
					>
						<SettingsIcon />
					</Popover.Trigger>
					<Popover.Content class="flex w-72 flex-col gap-5" align="start">
						<div
							class="flex items-center justify-between gap-4"
							role="group"
							aria-label="Number of songs"
						>
							<span class="text-sm font-medium">Songs:</span>
							<div class="flex items-center gap-3">
								<Button
									type="button"
									variant="outline"
									size="icon"
									aria-label="Fewer songs"
									disabled={isRunActive || count <= MIN_COUNT}
									onclick={() => count--}
								>
									<MinusIcon />
								</Button>
								<output
									class="w-8 text-center text-lg font-semibold tabular-nums"
									aria-label="Songs to find">{count}</output
								>
								<Button
									type="button"
									variant="outline"
									size="icon"
									aria-label="More songs"
									disabled={isRunActive || count >= MAX_COUNT}
									onclick={() => count++}
								>
									<PlusIcon />
								</Button>
							</div>
						</div>

						<div class="flex flex-col gap-3">
							<div class="flex items-center justify-between text-sm">
								<span id="exploration-label" class="font-medium"
									>Exploration</span
								>
								<output
									class="text-muted-foreground tabular-nums"
									aria-label="Exploration level">{exploration}%</output
								>
							</div>
							<Slider
								type="single"
								min={0}
								max={100}
								step={1}
								bind:value={exploration}
								disabled={isRunActive}
								aria-labelledby="exploration-label"
							/>
							<div class="flex justify-between text-xs text-muted-foreground">
								<span>Familiar</span>
								<span>Adventurous</span>
							</div>
						</div>
					</Popover.Content>
				</Popover.Root>
			</form>

			<p class="min-h-6 text-muted-foreground" aria-live="polite">
				{#if run.phase !== 'idle'}{run.status}{:else}{firstRunNotice}{/if}
			</p>
		{/if}

		{#if downloads.length > 0}
			<ul
				class={`flex w-full flex-col items-center gap-3 ${wasDownloadsVisible ? '' : REVEAL_CLASS}`}
			>
				{#each downloads as download (download.model)}
					<li class="flex w-full justify-center">
						<ModelDownload {download} state={download.state} />
					</li>
				{/each}
			</ul>
		{/if}
	</section>

	{#if isGridVisible}
		<section class="flex flex-col gap-3" aria-labelledby="recommended-heading">
			<div class="flex items-center justify-between">
				<h2
					id="recommended-heading"
					class={`text-2xl font-semibold ${gridRevealClass}`}
				>
					Recommended for you
				</h2>
				{#if isPlayVisible}
					<Button
						type="button"
						variant="outline"
						class={gridRevealClass}
						onclick={playAll}
					>
						<PlayIcon />
						Play All
					</Button>
				{/if}
			</div>
			<ul
				class="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4"
				aria-labelledby="recommended-heading"
			>
				{#each run.cards as card, index (getCardKey(card))}
					<li class={getCardRevealClass(card)}>
						{#if card.kind === 'loading'}
							<LoadingSongCard
								title={card.title}
								artist={card.artist}
								thumbnailUrl={card.thumbnail_url}
								albumArtUrl={card.album_art_url}
							/>
						{:else}
							<SongCard
								eager={index < 4}
								song={card.song}
								queue={songs}
								origin={RUN_QUEUE_ORIGIN}
							/>
						{/if}
					</li>
				{/each}
			</ul>
		</section>
	{:else if isEmpty}
		<p class="text-center text-muted-foreground">
			No new recommendations this time. Try again for a fresh batch.
		</p>
	{/if}
</main>

<TasteModal bind:open={isTasteModalOpen} />
