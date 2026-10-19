<script lang="ts">
	import { Button, buttonVariants } from '#lib/components/ui/button/index.js'
	import { Slider } from '#lib/components/ui/slider/index.js'
	import {
		attachPlayerHost,
		detachPlayerHost,
		player,
		playNext,
		playPrevious,
		seekTo,
		setVolume,
		toggleExpanded,
		toggleMute,
		togglePlayback,
	} from '#lib/player.svelte.js'
	import ChevronDownIcon from '@lucide/svelte/icons/chevron-down'
	import ChevronUpIcon from '@lucide/svelte/icons/chevron-up'
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link'
	import LoaderCircleIcon from '@lucide/svelte/icons/loader-circle'
	import MusicIcon from '@lucide/svelte/icons/music'
	import PauseIcon from '@lucide/svelte/icons/pause'
	import PlayIcon from '@lucide/svelte/icons/play'
	import SkipBackIcon from '@lucide/svelte/icons/skip-back'
	import SkipForwardIcon from '@lucide/svelte/icons/skip-forward'
	import Volume2Icon from '@lucide/svelte/icons/volume-2'
	import VolumeXIcon from '@lucide/svelte/icons/volume-x'
	import { onDestroy, onMount } from 'svelte'

	let hostElement: HTMLElement

	// Collapsed, the live video is covered by artwork so YouTube's own overlays never show.
	let failedArtUrl: string | null = $state(null)
	let artUrl = $derived.by(() => {
		const url = player.current?.album_art_url ?? player.current?.thumbnail_url
		return url && url !== failedArtUrl ? url : null
	})
	// Value shown while the user drags the seek thumb, before it is committed.
	let dragPosition: number | null = $state(null)

	let seekMax = $derived(Math.floor(player.duration) || 1)
	// The slider snaps off-step values and writes them back, so feed it whole seconds only.
	let seekValue = $derived(
		Math.min(Math.floor(dragPosition ?? player.position), seekMax)
	)
	let isLoading = $derived(player.status === 'loading')
	// A new song is loading (duration is reset); mid-song buffering keeps the video visible.
	let isSwitching = $derived(isLoading && player.duration === 0)
	let isPlaying = $derived(player.status === 'playing')
	let hasNext = $derived(player.index < player.queue.length - 1)
	let isVolumeMuted = $derived(player.muted || player.volume === 0)
	let subtitle = $derived(
		player.status === 'error' && player.error
			? player.error
			: (player.current?.artist ?? '')
	)

	// The video element keeps its DOM position; only its box is animated.
	let videoStyle = $derived(
		player.expanded
			? 'left: calc((100% - var(--video-width)) / 2); top: 56px; width: var(--video-width); height: calc(var(--video-width) * 9 / 16);'
			: 'left: 12px; top: 9px; width: 96px; height: 54px;'
	)
	let panelStyle = $derived(
		player.expanded
			? 'height: calc(var(--video-width) * 9 / 16 + 56px + 72px + 16px);'
			: 'height: 72px;'
	)

	function formatTime(seconds: number): string {
		const total = Math.max(0, Math.floor(seconds))
		const minutes = Math.floor(total / 60)
		const rest = String(total % 60).padStart(2, '0')
		return `${minutes}:${rest}`
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape' && player.expanded) toggleExpanded()
	}

	onMount(() => attachPlayerHost(hostElement))
	onDestroy(detachPlayerHost)
</script>

{#if player.expanded}
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-40 bg-black/60"
		data-testid="player-backdrop"
		onclick={toggleExpanded}
	></div>
{/if}

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div
	class="fixed inset-x-0 bottom-0 z-50 overflow-hidden border-t bg-card text-card-foreground transition-[height,transform] duration-300 motion-reduce:transition-none {player.current
		? 'translate-y-0'
		: 'translate-y-full'}"
	style="--video-width: min(calc(100vw - 2rem), calc((100vh - 12rem) * 16 / 9)); {panelStyle}"
	role="region"
	aria-label="Music player"
	inert={!player.current}
	onkeydown={handleKeydown}
>
	<p class="sr-only" aria-live="polite">
		{#if player.current}Now playing {player.current.title} by {player.current
				.artist}{/if}
	</p>

	{#if player.expanded && player.current}
		<div class="absolute inset-x-0 top-0 flex h-14 items-center gap-3 px-4">
			<div class="min-w-0 flex-1">
				<p class="truncate text-sm font-medium" title={player.current.title}>
					{player.current.title}
				</p>
				<p class="truncate text-sm text-muted-foreground">{subtitle}</p>
			</div>
			<Button
				variant="ghost"
				size="icon"
				aria-label="Collapse player"
				onclick={toggleExpanded}
			>
				<ChevronDownIcon />
			</Button>
		</div>
	{/if}

	<div
		bind:this={hostElement}
		class="absolute overflow-hidden rounded-md bg-black transition-[left,top,width,height] duration-300 motion-reduce:transition-none [&>iframe]:size-full {isSwitching
			? '[&>iframe]:invisible'
			: ''}"
		style={videoStyle}
		data-testid="player-video"
	>
		{#if !player.expanded}
			<div
				class="absolute inset-0 z-10 flex items-center justify-center bg-muted"
			>
				{#if artUrl}
					<img
						src={artUrl}
						alt=""
						class="size-full object-cover"
						onerror={() => (failedArtUrl = artUrl)}
					/>
				{:else}
					<MusicIcon class="size-5 text-muted-foreground" aria-hidden="true" />
				{/if}
			</div>
		{/if}
	</div>

	<div
		class="absolute inset-x-0 bottom-0 flex h-18 items-center gap-3 pr-3 transition-[padding] duration-300 motion-reduce:transition-none {player.expanded
			? 'pl-4'
			: 'pl-30'}"
	>
		{#if !player.expanded && player.current}
			<div class="min-w-0 flex-1 md:w-56 md:flex-none">
				<p class="truncate text-sm font-medium" title={player.current.title}>
					{player.current.title}
				</p>
				<p class="truncate text-xs text-muted-foreground">{subtitle}</p>
			</div>
		{/if}

		<div class="flex items-center">
			<Button
				variant="ghost"
				size="icon"
				aria-label="Previous song"
				disabled={!player.current}
				onclick={playPrevious}
			>
				<SkipBackIcon />
			</Button>
			<Button
				variant="ghost"
				size="icon"
				aria-label={isLoading ? 'Loading' : isPlaying ? 'Pause' : 'Play'}
				disabled={!player.current || isLoading}
				onclick={togglePlayback}
			>
				{#if isLoading}
					<LoaderCircleIcon class="animate-spin motion-reduce:animate-none" />
				{:else if isPlaying}
					<PauseIcon />
				{:else}
					<PlayIcon />
				{/if}
			</Button>
			<Button
				variant="ghost"
				size="icon"
				aria-label="Next song"
				disabled={!player.current || !hasNext}
				onclick={playNext}
			>
				<SkipForwardIcon />
			</Button>
		</div>

		<div
			class="items-center gap-2 text-xs text-muted-foreground tabular-nums {player.expanded
				? 'flex flex-1'
				: 'hidden flex-1 md:flex'}"
		>
			<span>{formatTime(seekValue)}</span>
			<Slider
				type="single"
				min={0}
				max={seekMax}
				step={1}
				bind:value={() => seekValue, (value) => (dragPosition = value)}
				onValueCommit={(value) => {
					seekTo(value)
					dragPosition = null
				}}
				disabled={!player.current || player.duration === 0}
				aria-label="Seek"
				valueText="{formatTime(seekValue)} of {formatTime(player.duration)}"
			/>
			<span>{formatTime(player.duration)}</span>
		</div>

		<div class="group hidden items-center md:flex">
			<Button
				variant="ghost"
				size="icon"
				aria-label={isVolumeMuted ? 'Unmute' : 'Mute'}
				onclick={toggleMute}
			>
				{#if isVolumeMuted}<VolumeXIcon />{:else}<Volume2Icon />{/if}
			</Button>
			<div
				class="w-0 overflow-hidden transition-[width] group-focus-within:w-24 group-hover:w-24 motion-reduce:transition-none"
			>
				<Slider
					type="single"
					min={0}
					max={100}
					step={1}
					class="mx-1 w-20"
					bind:value={
						() => (player.muted ? 0 : player.volume),
						(value) => setVolume(value)
					}
					aria-label="Volume"
					valueText="{player.muted ? 0 : player.volume}%"
				/>
			</div>
		</div>

		{#if player.current}
			<a
				class={buttonVariants({ variant: 'ghost', size: 'icon' })}
				href={player.current.url}
				target="_blank"
				rel="noopener noreferrer"
				aria-label="Open on YouTube"
			>
				<ExternalLinkIcon />
			</a>
		{/if}

		{#if !player.expanded}
			<Button
				variant="ghost"
				size="icon"
				aria-label="Expand player"
				onclick={toggleExpanded}
			>
				<ChevronUpIcon />
			</Button>
		{/if}
	</div>
</div>
