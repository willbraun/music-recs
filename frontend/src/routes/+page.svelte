<script lang="ts">
	import LoadingSongCard from '#lib/components/LoadingSongCard.svelte'
	import SongCard from '#lib/components/SongCard.svelte'
	import { Button, buttonVariants } from '#lib/components/ui/button/index.js'
	import * as Popover from '#lib/components/ui/popover/index.js'
	import { run, startNewRun, type RunCard } from '#lib/run.svelte.js'
	import MinusIcon from '@lucide/svelte/icons/minus'
	import PlusIcon from '@lucide/svelte/icons/plus'
	import SettingsIcon from '@lucide/svelte/icons/settings'
	import SparklesIcon from '@lucide/svelte/icons/sparkles'

	const MIN_COUNT = 1
	const MAX_COUNT = 50

	let count = $state(3)

	let isRunActive = $derived(run.phase === 'preparing' || run.phase === 'streaming')
	let hasRecommendations = $derived(run.cards.some(card => card.kind === 'song'))
	let isGridVisible = $derived(run.phase !== 'idle' && run.phase !== 'preparing' && run.cards.length > 0)
	let isEmpty = $derived(run.phase === 'done' && !hasRecommendations)

	function getCardKey(card: RunCard): string {
		return card.kind === 'loading' ? card.video_id : card.song.video_id
	}

	function submitRun(event: SubmitEvent) {
		event.preventDefault()
		if (!isRunActive) void startNewRun(count)
	}
</script>

<svelte:head>
	<title>Discover something new</title>
</svelte:head>

<main class="mx-auto flex max-w-7xl flex-col gap-10 px-6 py-12">
	<section class="flex flex-col items-center gap-6 text-center">
		<div class="flex flex-col gap-2">
			<h1 class="text-3xl font-semibold tracking-tight">Discover something new</h1>
			<p class="text-muted-foreground">Based on your taste, I'll find music you might like.</p>
		</div>

		<form class="flex items-center gap-2 relative" onsubmit={submitRun}>
			<Button type="submit" size="lg" disabled={isRunActive}>
				<SparklesIcon />
				{isRunActive ? 'Finding music...' : 'Find new music'}
			</Button>

			<Popover.Root>
				<Popover.Trigger
					type="button"
					class={`${buttonVariants({ variant: 'outline', size: 'icon-lg' })} absolute -right-12`}
					aria-label="Settings"
				>
					<SettingsIcon />
				</Popover.Trigger>
				<Popover.Content class="w-auto" align="start">
					<div class="flex items-center gap-4" role="group" aria-label="Number of songs">
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
							<output class="w-8 text-center text-lg font-semibold tabular-nums" aria-label="Songs to find"
								>{count}</output
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
				</Popover.Content>
			</Popover.Root>
		</form>

		<p class="text-muted-foreground min-h-6" aria-live="polite">
			{#if run.phase !== 'idle'}{run.status}{/if}
		</p>
	</section>

	{#if isGridVisible}
		<section class="flex flex-col gap-3" aria-labelledby="recommended-heading">
			<h2 id="recommended-heading" class="text-lg font-semibold">Recommended for you</h2>
			<ul class="grid grid-cols-4 gap-4" aria-labelledby="recommended-heading">
				{#each run.cards as card (getCardKey(card))}
					<li>
						{#if card.kind === 'loading'}
							<LoadingSongCard title={card.title} artist={card.artist} />
						{:else}
							<SongCard song={card.song} />
						{/if}
					</li>
				{/each}
			</ul>
		</section>
	{:else if isEmpty}
		<p class="text-muted-foreground text-center">No new recommendations this time. Try again for a fresh batch.</p>
	{/if}
</main>
