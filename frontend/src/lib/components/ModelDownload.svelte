<script lang="ts">
	import type { ModelDownload } from '#lib/api.js'
	import { Progress } from '#lib/components/ui/progress/index.js'
	import { formatBytes, formatDuration, formatSpeed } from '#lib/format.js'

	let { download }: { download: ModelDownload } = $props()

	let percent = $derived(
		download.total_bytes
			? Math.min(
					Math.floor((download.downloaded_bytes / download.total_bytes) * 100),
					100
				)
			: null
	)
</script>

<section
	class="flex w-full max-w-md flex-col gap-2 rounded-lg border p-4 text-left text-sm"
	aria-label="Model download"
>
	<div class="flex items-center justify-between gap-4">
		<span class="truncate font-medium">{download.model}</span>
		{#if percent !== null}
			<span class="text-muted-foreground tabular-nums">{percent}%</span>
		{/if}
	</div>
	<Progress
		value={percent}
		aria-label={`Downloading ${download.model}`}
		class={percent === null
			? 'animate-pulse **:data-[slot=progress-indicator]:transform-none!'
			: ''}
	/>
	<div class="flex items-center gap-2 text-muted-foreground tabular-nums">
		{#if download.total_bytes}
			{formatBytes(download.downloaded_bytes)} of {formatBytes(
				download.total_bytes
			)}
		{:else}
			{formatBytes(download.downloaded_bytes)}
		{/if}
		{#if download.bytes_per_second > 0}
			<span>•</span>
			{formatSpeed(download.bytes_per_second)}
		{/if}
		<span class="ml-auto tabular-nums">
			{#if download.bytes_per_second > 0 && download.seconds_remaining !== null}
				{formatDuration(download.seconds_remaining)} left
			{/if}
		</span>
	</div>
</section>
