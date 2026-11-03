<script lang="ts">
	import type { ModelDownload, ModelDownloadState } from '#lib/api.js'
	import { Progress } from '#lib/components/ui/progress/index.js'
	import { formatBytes, formatDuration, formatSpeed } from '#lib/format.js'
	import { findModel } from '#lib/models.js'
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link'

	let {
		download,
		state = 'downloading',
	}: { download: ModelDownload; state?: ModelDownloadState } = $props()

	let model = $derived(findModel(download.model))
	let percent = $derived(
		state === 'done'
			? 100
			: state === 'pending'
				? 0
				: download.total_bytes
					? Math.min(
							Math.floor(
								(download.downloaded_bytes / download.total_bytes) * 100
							),
							100
						)
					: null
	)
	let progressLabel = $derived(
		state === 'pending'
			? `Waiting to download ${model.name}`
			: state === 'done'
				? `Downloaded ${model.name}`
				: `Downloading ${model.name}`
	)
</script>

<section
	class="flex w-full max-w-md flex-col gap-2 rounded-lg border p-4 text-left text-sm"
	aria-label="Model download"
>
	<div class="flex items-center justify-between gap-4">
		<span class="flex min-w-0 items-center gap-1.5">
			<span class="truncate font-medium">{model.name}</span>
			<a
				class="shrink-0 rounded-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
				href={model.url}
				target="_blank"
				rel="noopener noreferrer"
				aria-label="Open {model.name} on Hugging Face"
				title="Open on Hugging Face"
			>
				<ExternalLinkIcon class="size-4" />
			</a>
		</span>
		{#if state !== 'pending' && percent !== null}
			<span class="text-muted-foreground tabular-nums">{percent}%</span>
		{/if}
	</div>
	<Progress
		value={percent}
		aria-label={progressLabel}
		class={percent === null
			? 'animate-pulse **:data-[slot=progress-indicator]:transform-none!'
			: ''}
	/>
	<div class="flex items-center gap-2 text-muted-foreground tabular-nums">
		{#if state === 'pending' || state === 'done'}
			{state === 'pending' ? 'Waiting' : 'Downloaded'}
			{#if download.total_bytes}
				<span>•</span>
				{formatBytes(download.total_bytes)}
			{/if}
		{:else}
			{#if download.total_bytes}
				{formatBytes(download.downloaded_bytes)} of {formatBytes(
					download.total_bytes
				)}
			{:else}
				{formatBytes(download.downloaded_bytes)}
			{/if}
			<span>•</span>
			{#if download.bytes_per_second > 0}
				{formatSpeed(download.bytes_per_second)}
			{:else}
				Waiting...
			{/if}
			<span class="ml-auto tabular-nums">
				{#if download.bytes_per_second > 0 && download.seconds_remaining !== null}
					{formatDuration(download.seconds_remaining)} left
				{/if}
			</span>
		{/if}
	</div>
</section>
