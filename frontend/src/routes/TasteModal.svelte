<script lang="ts">
	import ModelDownload from '#lib/components/ModelDownload.svelte'
	import { Button } from '#lib/components/ui/button/index.js'
	import * as Dialog from '#lib/components/ui/dialog/index.js'
	import { formatBytes } from '#lib/format.js'
	import {
		areModelsDownloaded,
		downloadMissingModels,
		getActiveDownloads,
		getMissingModels,
		getMissingModelsSize,
		modelCache,
	} from '#lib/modelCache.svelte.js'
	import { findModel, MODELS } from '#lib/models.js'
	import DownloadIcon from '@lucide/svelte/icons/download'
	import TasteForm from './taste/TasteForm.svelte'

	let { open = $bindable(false) }: { open?: boolean } = $props()

	let isStarting = $state(false)
	// Keeps the "ready" note once the models finish while the modal is open.
	let hadMissingModels = $state(false)

	let downloads = $derived(getActiveDownloads())
	let isReady = $derived(areModelsDownloaded())
	let pendingModels = $derived(
		getMissingModels().map((item) => ({
			...findModel(item.id),
			purpose: MODELS.find((model) => model.id === item.id)?.purpose,
		}))
	)
	let failures = $derived(
		getMissingModels().filter((item) => item.download?.state === 'failed')
	)
	let size = $derived(getMissingModelsSize())

	$effect(() => {
		if (modelCache.status === 'ready' && !isReady) hadMissingModels = true
	})

	async function startDownload() {
		isStarting = true
		try {
			await downloadMissingModels()
		} finally {
			isStarting = false
		}
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Content class="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
		<Dialog.Header>
			<Dialog.Title class="text-xl font-semibold"
				>What music do you like?</Dialog.Title
			>
			<Dialog.Description>
				Your preferences are used to improve your music recommendations.
			</Dialog.Description>
		</Dialog.Header>

		{#if modelCache.status === 'ready' && !isReady}
			<section
				class="flex flex-col gap-3 rounded-lg border p-4"
				aria-labelledby="model-prep-heading"
			>
				{#if downloads.length > 0}
					<h3 id="model-prep-heading" class="font-medium">
						Downloading models...
					</h3>
					<ul class="flex flex-col gap-3">
						{#each downloads as download (download.model)}
							<li>
								<ModelDownload {download} state={download.state} />
							</li>
						{/each}
					</ul>
					<p class="text-muted-foreground">
						You can continue entering your preferences while they download.
					</p>
				{:else}
					<h3 id="model-prep-heading" class="font-medium">
						Get ready to discover
					</h3>
					<p class="text-muted-foreground">
						Download the AI models needed to generate recommendations locally.
					</p>
					<ul class="flex flex-col gap-2" aria-label="Models to download">
						{#each pendingModels as model (model.id)}
							<li class="flex flex-col">
								<span class="font-medium">{model.name}</span>
								{#if model.purpose}
									<span class="text-muted-foreground">{model.purpose}</span>
								{/if}
							</li>
						{/each}
					</ul>
					<p class="text-muted-foreground">
						{#if size !== null}About {formatBytes(size)},
						{/if}{' '}this may take a while
					</p>
					{#each failures as item (item.id)}
						<p class="text-destructive" role="alert">
							{findModel(item.id).name}: {item.download?.error ??
								'Download failed'}
						</p>
					{/each}
					<div class="flex flex-wrap items-center gap-3">
						<Button type="button" disabled={isStarting} onclick={startDownload}>
							<DownloadIcon />
							{failures.length > 0 ? 'Retry Download' : 'Download Models'}
						</Button>
						<span class="text-sm text-muted-foreground">
							Recommended while you enter your preferences.
						</span>
					</div>
				{/if}
			</section>
		{:else if isReady && hadMissingModels}
			<p class="rounded-lg border p-4 font-medium" aria-live="polite">
				Models ready
			</p>
		{/if}

		<TasteForm saveLabel="Save" onsaved={() => (open = false)} />
	</Dialog.Content>
</Dialog.Root>
