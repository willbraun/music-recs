<script lang="ts">
	import { Button } from '#lib/components/ui/button/index.js'
	import { Skeleton } from '#lib/components/ui/skeleton/index.js'
	import {
		downloadModel,
		loadModelCache,
		modelCache,
		removeModelFiles,
		watchModelCache,
	} from '#lib/modelCache.svelte.js'
	import { MODELS } from '#lib/models.js'
	import { onMount } from 'svelte'
	import ModelCard from './ModelCard.svelte'

	onMount(watchModelCache)
</script>

<svelte:head>
	<title>Models</title>
</svelte:head>

<main class="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-12">
	<div class="flex flex-col gap-2">
		<h1 class="text-3xl font-semibold tracking-tight">Models</h1>
		<p class="text-muted-foreground">
			The models that run on this computer. They download automatically when a
			run needs them, or you can download or remove them here.
		</p>
	</div>

	{#if modelCache.status === 'loading'}
		<div
			class="flex flex-col gap-4"
			aria-busy="true"
			aria-label="Loading models"
		>
			{#each MODELS as model (model.id)}
				<Skeleton class="h-56 w-full" />
			{/each}
		</div>
	{:else if modelCache.status === 'error'}
		<div class="flex flex-col items-center gap-3 py-12 text-center">
			<p class="text-muted-foreground">{modelCache.error}</p>
			<Button type="button" variant="outline" onclick={loadModelCache}>
				Retry
			</Button>
		</div>
	{:else}
		<ul class="flex flex-col gap-4">
			{#each modelCache.items as status (status.id)}
				{@const info = MODELS.find((model) => model.id === status.id)}
				{#if info}
					<li>
						<ModelCard
							{info}
							{status}
							isBusy={modelCache.busy}
							isRemoving={modelCache.removing.includes(status.id)}
							onDownload={() => downloadModel(status.id)}
							onRemove={() => removeModelFiles(status.id)}
						/>
					</li>
				{/if}
			{/each}
		</ul>
	{/if}
</main>
