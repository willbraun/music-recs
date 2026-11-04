<script lang="ts">
	import type { LicenseText } from '#lib/licenses.js'
	import { afterNavigate } from '$app/navigation'
	import ArrowLeftIcon from '@lucide/svelte/icons/arrow-left'

	let { license }: { license: LicenseText } = $props()

	// Reached from About or Models; a direct visit falls back to About.
	let backPath = $state('/about')
	afterNavigate(({ from }) => {
		if (from) backPath = from.url.pathname
	})
</script>

<svelte:head>
	<title>{license.title}</title>
</svelte:head>

<main class="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-12">
	<div class="flex flex-col gap-3">
		<a
			class="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground underline-offset-4 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring"
			href={backPath}
		>
			<ArrowLeftIcon class="size-3.5" />
			Back
		</a>
		<h1 class="text-3xl font-semibold tracking-tight">{license.title}</h1>
	</div>

	{#each license.sections as section, index (index)}
		<section class="flex flex-col gap-2 text-sm">
			{#if section.heading}
				<h2 class="text-base font-semibold">{section.heading}</h2>
			{/if}
			{#each section.paragraphs as paragraph (paragraph)}
				<p class="text-muted-foreground">{paragraph}</p>
			{/each}
		</section>
	{/each}
</main>
