<script lang="ts">
	import DiscardTasteDialog from '#lib/components/DiscardTasteDialog.svelte'
	import Header from '#lib/components/Header.svelte'
	import Player from '#lib/components/Player.svelte'
	import SwitchProfileDialog from '#lib/components/SwitchProfileDialog.svelte'
	import { Button } from '#lib/components/ui/button/index.js'
	import { Toaster } from '#lib/components/ui/sonner/index.js'
	import { handleExternalLinkClick } from '#lib/links.js'
	import { player } from '#lib/player.svelte.js'
	import { loadProfiles, profiles } from '#lib/profiles.svelte.js'
	import { closeRunStream, resumeRun } from '#lib/run.svelte.js'
	import { loadTaste } from '#lib/taste.svelte.js'
	import { startAutoUpdateCheck } from '#lib/update.svelte.js'
	import { goto } from '$app/navigation'
	import { page } from '$app/state'
	import { ModeWatcher } from 'mode-watcher'
	import { onDestroy, onMount } from 'svelte'
	import type { LayoutProps } from './$types'
	import './layout.css'

	// Reachable before a profile is chosen; they render without the header.
	const PROFILE_PATHS = ['/profiles', '/add-profile']

	let { children }: LayoutProps = $props()

	const isProfilePage = $derived(PROFILE_PATHS.includes(page.url.pathname))
	const hasProfile = $derived(
		profiles.status === 'ready' && profiles.activeId !== null
	)

	onMount(() => {
		void loadProfiles().then(() => {
			if (profiles.activeId === null) return
			void loadTaste()
			resumeRun()
		})
		return startAutoUpdateCheck()
	})
	onDestroy(closeRunStream)

	// No profile chosen in this tab: pick one, or create the first.
	$effect(() => {
		if (profiles.status !== 'ready' || hasProfile || isProfilePage) return
		void goto(profiles.items.length > 0 ? '/profiles' : '/add-profile', {
			replaceState: true,
		})
	})
</script>

<svelte:document onclick={handleExternalLinkClick} />

<ModeWatcher defaultMode="dark" />
<Toaster />
<DiscardTasteDialog />
<SwitchProfileDialog />

{#if hasProfile && !isProfilePage}
	<Header />
{/if}

<div class:pb-18={player.current}>
	{#if isProfilePage || hasProfile}
		{@render children()}
	{:else if profiles.status === 'error'}
		<div class="flex flex-col items-center gap-3 py-24 text-center">
			<p class="text-muted-foreground">{profiles.error}</p>
			<Button type="button" variant="outline" onclick={loadProfiles}
				>Retry</Button
			>
		</div>
	{/if}
</div>

<Player />
