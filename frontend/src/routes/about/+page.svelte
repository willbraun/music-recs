<script lang="ts">
	const STEPS = [
		'Your taste profile describes the genres and artists you like and dislike.',
		'A language model turns that taste into search queries, unless you search for something yourself.',
		'The queries are searched on YouTube Music, and a short clip is taken from the middle of each studio song.',
		'An audio model listens to each clip and decides whether you would like it, with a confidence score.',
		'Songs you would like are recommended, and album artwork is looked up for each one.',
	]

	// Estimates from the model sizes, not measured minimums.
	const REQUIREMENTS = [
		{
			name: 'Disk Space',
			detail:
				'About 14 GB free for the two models, which are stored in the Hugging Face cache.',
		},
		{
			name: 'Memory (VRAM)',
			detail:
				'16 GB or more of unified memory. The models load one at a time, so Qwen 2.5 3B (about 6 GB of weights) and MOSS Music (about 8 GB at peak) each fit within it.',
		},
		{
			name: 'Processor',
			detail: 'Apple Silicon, which the MLX build of the audio model requires.',
		},
		{
			name: 'Operating System',
			detail: 'macOS.',
		},
		{
			name: 'Internet',
			detail:
				'Needed to download the models from Hugging Face, search and fetch audio from YouTube Music, and look up artwork from MusicBrainz and the Cover Art Archive.',
		},
	]
</script>

<svelte:head>
	<title>About</title>
</svelte:head>

<main class="mx-auto flex max-w-3xl flex-col gap-10 px-6 py-12">
	<div class="flex flex-col gap-2">
		<h1 class="text-3xl font-semibold tracking-tight">About</h1>
		<p class="text-muted-foreground">
			Music Recs finds music online, analyzes it with an audio model running on
			this computer, and recommends songs based on your musical taste. Your
			taste and the songs it analyzes are stored locally.
		</p>
	</div>

	<section class="flex flex-col gap-3" aria-labelledby="how-heading">
		<h2 id="how-heading" class="text-xl font-semibold">How It Works</h2>
		<ol class="flex list-decimal flex-col gap-1.5 pl-5 text-muted-foreground">
			{#each STEPS as step (step)}
				<li>{step}</li>
			{/each}
		</ol>
	</section>

	<section class="flex flex-col gap-3" aria-labelledby="requirements-heading">
		<h2 id="requirements-heading" class="text-xl font-semibold">
			System Requirements
		</h2>
		<dl class="flex flex-col divide-y rounded-lg border text-sm">
			{#each REQUIREMENTS as requirement (requirement.name)}
				<div class="flex flex-col gap-1 p-4 sm:flex-row sm:gap-6">
					<dt class="w-36 shrink-0 font-medium">{requirement.name}</dt>
					<dd class="text-muted-foreground">{requirement.detail}</dd>
				</div>
			{/each}
		</dl>
	</section>
</main>
