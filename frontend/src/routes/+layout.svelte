<script lang="ts">
	import favicon from '#lib/assets/favicon.svg'
	import Header from '#lib/components/Header.svelte'
	import Player from '#lib/components/Player.svelte'
	import { Toaster } from '#lib/components/ui/sonner/index.js'
	import { player } from '#lib/player.svelte.js'
	import { closeRunStream, resumeRun } from '#lib/run.svelte.js'
	import { ModeWatcher } from 'mode-watcher'
	import { onDestroy, onMount } from 'svelte'
	import type { LayoutProps } from './$types'
	import './layout.css'
	import TasteGate from './taste/TasteGate.svelte'

	let { children }: LayoutProps = $props()

	onMount(resumeRun)
	onDestroy(closeRunStream)
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<ModeWatcher defaultMode="dark" />
<Toaster />

<Header />

<div class:pb-18={player.current}>
	<TasteGate>
		{@render children()}
	</TasteGate>
</div>

<Player />
