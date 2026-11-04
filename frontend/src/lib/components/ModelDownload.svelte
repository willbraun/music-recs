<script lang="ts">
	import type { ModelDownload, ModelDownloadState } from '#lib/api.js'
	import { findModel } from '#lib/models.js'
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link'
	import DownloadProgress from './DownloadProgress.svelte'

	let {
		download,
		state = 'downloading',
	}: { download: ModelDownload; state?: ModelDownloadState } = $props()

	let model = $derived(findModel(download.model))
</script>

<section
	class="flex w-full max-w-md flex-col gap-2 rounded-lg border p-4 text-left text-sm"
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
	<DownloadProgress {download} {state} name={model.name} />
</section>
