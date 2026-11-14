<script lang="ts">
	import type { ModelDownload, ModelDownloadState } from '#lib/api.js'
	import { findModel, MODELS } from '#lib/models.js'
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link'
	import DownloadProgress from './DownloadProgress.svelte'

	// Without a download, the panel is the pre-download state and shows the model's purpose.
	let {
		download,
		modelId,
		state = 'downloading',
	}: {
		download?: ModelDownload
		modelId?: string
		state?: ModelDownloadState
	} = $props()

	let model = $derived(findModel(modelId ?? download?.model ?? ''))
	let purpose = $derived(MODELS.find((item) => item.id === model.id)?.purpose)
</script>

<section
	class="flex w-full flex-col gap-2 rounded-lg border p-4 text-left text-sm"
	aria-label="Model download"
>
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
	{#if download}
		<DownloadProgress {download} {state} name={model.name} />
	{:else if purpose}
		<p class="text-muted-foreground">{purpose}</p>
	{/if}
</section>
