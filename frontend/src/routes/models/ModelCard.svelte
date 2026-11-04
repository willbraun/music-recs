<script lang="ts">
	import type { ModelStatus } from '#lib/api.js'
	import DownloadProgress from '#lib/components/DownloadProgress.svelte'
	import { Badge, type BadgeVariant } from '#lib/components/ui/badge/index.js'
	import { Button } from '#lib/components/ui/button/index.js'
	import * as Dialog from '#lib/components/ui/dialog/index.js'
	import { formatBytes } from '#lib/format.js'
	import type { ModelInfo } from '#lib/models.js'
	import DownloadIcon from '@lucide/svelte/icons/download'
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link'
	import Trash2Icon from '@lucide/svelte/icons/trash-2'

	let {
		info,
		status,
		isBusy,
		isRemoving,
		onDownload,
		onRemove,
	}: {
		info: ModelInfo
		status: ModelStatus
		// A run or download is queued or running, so the model cannot be removed.
		isBusy: boolean
		isRemoving: boolean
		onDownload: () => void
		onRemove: () => void
	} = $props()

	let isConfirmOpen = $state(false)

	let download = $derived(status.download)
	let activeDownload = $derived(
		download?.state === 'pending' || download?.state === 'downloading'
			? { ...download, state: download.state }
			: null
	)
	let badge = $derived.by((): { label: string; variant: BadgeVariant } => {
		if (status.downloaded) return { label: 'Downloaded', variant: 'default' }
		if (download?.state === 'pending')
			return { label: 'Queued', variant: 'secondary' }
		if (download?.state === 'downloading')
			return { label: 'Downloading', variant: 'secondary' }
		if (download?.state === 'failed')
			return { label: 'Download failed', variant: 'destructive' }
		return { label: 'Not downloaded', variant: 'outline' }
	})

	function confirmRemove() {
		isConfirmOpen = false
		onRemove()
	}
</script>

<section
	class="flex flex-col gap-4 rounded-lg border p-5 text-sm"
	aria-labelledby="model-{info.id}-name"
>
	<div class="flex items-start justify-between gap-4">
		<div class="flex min-w-0 items-center gap-2">
			<h2 id="model-{info.id}-name" class="truncate text-lg font-semibold">
				{info.name}
			</h2>
			<a
				class="shrink-0 rounded-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
				href={info.url}
				target="_blank"
				rel="noopener noreferrer"
				aria-label="Open {info.name} on Hugging Face"
				title="Open on Hugging Face"
			>
				<ExternalLinkIcon class="size-4" />
			</a>
		</div>
		<Badge variant={badge.variant}>{badge.label}</Badge>
	</div>

	<p class="text-muted-foreground">{info.purpose}</p>

	<dl class="flex flex-wrap gap-x-8 gap-y-1">
		<div class="flex gap-2">
			<dt class="text-muted-foreground">Size</dt>
			<dd class="font-medium tabular-nums">
				{status.size_bytes === null
					? 'Unknown'
					: formatBytes(status.size_bytes)}
			</dd>
		</div>
	</dl>

	{#if activeDownload}
		<DownloadProgress
			download={activeDownload}
			state={activeDownload.state}
			name={info.name}
		/>
	{:else if download?.state === 'failed'}
		<p class="text-destructive" role="alert">
			{download.error ?? 'The download failed.'}
		</p>
	{/if}

	{#if !status.downloaded && !activeDownload}
		<div>
			<Button
				type="button"
				variant="outline"
				aria-label="{download?.state === 'failed'
					? 'Retry'
					: 'Download'} {info.name}"
				onclick={onDownload}
			>
				<DownloadIcon />
				{download?.state === 'failed' ? 'Retry' : 'Download'}
			</Button>
		</div>
	{:else if status.downloaded}
		<div class="flex flex-wrap items-center gap-3">
			<Button
				type="button"
				variant="outline"
				aria-label="Remove {info.name}"
				disabled={isBusy || isRemoving}
				onclick={() => (isConfirmOpen = true)}
			>
				<Trash2Icon />
				{isRemoving ? 'Removing...' : 'Remove'}
			</Button>
			{#if isBusy && !isRemoving}
				<span class="text-muted-foreground">
					Available once the current run or download finishes.
				</span>
			{/if}
		</div>
	{/if}
</section>

<Dialog.Root bind:open={isConfirmOpen}>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title>Remove {info.name}?</Dialog.Title>
			<Dialog.Description>
				This deletes the downloaded files
				{#if status.size_bytes !== null}
					({formatBytes(status.size_bytes)})
				{/if}
				from this computer. The next run that needs the model downloads it again.
			</Dialog.Description>
		</Dialog.Header>
		<Dialog.Footer>
			<Dialog.Close>
				{#snippet child({ props })}
					<Button variant="outline" {...props}>Cancel</Button>
				{/snippet}
			</Dialog.Close>
			<Button type="button" variant="destructive" onclick={confirmRemove}>
				Remove
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
