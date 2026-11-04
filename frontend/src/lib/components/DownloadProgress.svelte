<script lang="ts">
	import type { ModelDownload, ModelDownloadState } from '#lib/api.js'
	import { Progress } from '#lib/components/ui/progress/index.js'
	import { formatBytes, formatDuration, formatSpeed } from '#lib/format.js'

	let {
		download,
		state,
		name,
	}: {
		download: Omit<ModelDownload, 'model'>
		state: ModelDownloadState
		name: string
	} = $props()

	let percent = $derived(
		state === 'pending'
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
		state === 'pending' ? `Waiting to download ${name}` : `Downloading ${name}`
	)
</script>

<div class="flex w-full flex-col gap-2 text-sm">
	<Progress
		value={percent}
		aria-label={progressLabel}
		class={percent === null
			? 'animate-pulse **:data-[slot=progress-indicator]:transform-none!'
			: ''}
	/>
	<div class="flex items-center gap-2 text-muted-foreground tabular-nums">
		{#if state === 'pending'}
			Waiting
			{#if download.total_bytes}
				<span>•</span>
				{formatBytes(download.total_bytes)}
			{/if}
		{:else}
			{#if percent !== null}
				<span>{percent}%</span>
				<span>•</span>
			{/if}
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
</div>
