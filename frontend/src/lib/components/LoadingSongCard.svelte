<script lang="ts">
	import LoaderCircleIcon from '@lucide/svelte/icons/loader-circle'

	let { title, artist }: { title: string; artist: string } = $props()
</script>

<article class="w-full" aria-busy="true" aria-label="Analyzing {title}">
	<div
		class="relative flex aspect-square items-center justify-center rounded-lg bg-muted"
	>
		<LoaderCircleIcon
			class="size-8 animate-spin text-muted-foreground motion-reduce:animate-none"
			aria-hidden="true"
		/>
	</div>
	<div class="mt-2 min-w-0 opacity-60">
		<p class="truncate text-sm font-medium" {title}>{title}</p>
		<p class="truncate text-sm text-muted-foreground">{artist}</p>
	</div>
</article>
