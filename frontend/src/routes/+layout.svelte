<script lang="ts">
	import DiscardTasteDialog from '#lib/components/DiscardTasteDialog.svelte'
	import Header from '#lib/components/Header.svelte'
	import Player from '#lib/components/Player.svelte'
	import { Toaster } from '#lib/components/ui/sonner/index.js'
	import { handleExternalLinkClick } from '#lib/links.js'
	import { player } from '#lib/player.svelte.js'
	import { closeRunStream, resumeRun } from '#lib/run.svelte.js'
	import { loadTaste } from '#lib/taste.svelte.js'
	import { startAutoUpdateCheck } from '#lib/update.svelte.js'
	import { ModeWatcher } from 'mode-watcher'
	import { onDestroy, onMount } from 'svelte'
	import type { LayoutProps } from './$types'
	import './layout.css'

	let { children }: LayoutProps = $props()

	onMount(() => {
		void loadTaste()
		resumeRun()
		return startAutoUpdateCheck()
	})
	onDestroy(closeRunStream)
</script>

<svelte:document onclick={handleExternalLinkClick} />

<ModeWatcher defaultMode="dark" />
<Toaster />
<DiscardTasteDialog />

<Header />

<div class:pb-18={player.current}>
	{@render children()}
</div>

<Player />
