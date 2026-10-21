<script lang="ts">
	import { Button } from '#lib/components/ui/button/index.js'
	import { Skeleton } from '#lib/components/ui/skeleton/index.js'
	import { loadTaste, taste } from '#lib/taste.svelte.js'
	import TasteForm from './TasteForm.svelte'
</script>

<svelte:head>
	<title>Your taste</title>
</svelte:head>

<main class="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-12">
	<div class="flex flex-col gap-2">
		<h1 class="text-3xl font-semibold tracking-tight">Your taste</h1>
		{#if taste.status === 'none'}
			<p class="text-muted-foreground">Tell us what you like to get started.</p>
		{/if}
	</div>

	{#if taste.status === 'loading'}
		<div
			class="flex flex-col gap-6"
			aria-busy="true"
			aria-label="Loading taste"
		>
			<Skeleton class="h-9 w-full" />
			<Skeleton class="h-9 w-full" />
			<Skeleton class="h-9 w-full" />
			<Skeleton class="h-9 w-full" />
			<Skeleton class="h-24 w-full" />
		</div>
	{:else if taste.status === 'error'}
		<div class="flex flex-col items-center gap-3 py-12 text-center">
			<p class="text-muted-foreground">{taste.error}</p>
			<Button type="button" variant="outline" onclick={loadTaste}>Retry</Button>
		</div>
	{:else}
		<TasteForm />
		{#if taste.current}
			<section class="flex flex-col gap-2">
				<h2 class="text-lg font-medium">What the model sees</h2>
				<p
					class="rounded-lg border bg-muted/50 p-4 text-sm whitespace-pre-wrap"
				>
					{taste.current.text}
				</p>
			</section>
		{/if}
	{/if}
</main>
