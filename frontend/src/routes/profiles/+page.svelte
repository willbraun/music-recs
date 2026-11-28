<script lang="ts">
	import ProfileAvatar from '#lib/components/ProfileAvatar.svelte'
	import { Button } from '#lib/components/ui/button/index.js'
	import { Skeleton } from '#lib/components/ui/skeleton/index.js'
	import {
		loadProfiles,
		profiles,
		requestProfileSwitch,
	} from '#lib/profiles.svelte.js'
	import { goto } from '$app/navigation'
	import PlusIcon from '@lucide/svelte/icons/plus'

	function chooseProfile(id: number) {
		if (requestProfileSwitch(id)) void goto('/')
	}
</script>

<svelte:head>
	<title>Choose a profile</title>
</svelte:head>

<main class="mx-auto flex max-w-3xl flex-col items-center gap-10 px-6 py-24">
	<h1 class="text-4xl font-semibold tracking-tight">Who's listening?</h1>

	{#if profiles.status === 'loading'}
		<div class="flex gap-6" aria-busy="true" aria-label="Loading profiles">
			<Skeleton class="size-32 rounded-md" />
			<Skeleton class="size-32 rounded-md" />
		</div>
	{:else if profiles.status === 'error'}
		<div class="flex flex-col items-center gap-3 text-center">
			<p class="text-muted-foreground">{profiles.error}</p>
			<Button type="button" variant="outline" onclick={loadProfiles}
				>Retry</Button
			>
		</div>
	{:else}
		<ul class="flex flex-wrap justify-center gap-8">
			{#each profiles.items as profile (profile.id)}
				<li>
					<button
						type="button"
						class="group flex w-32 cursor-pointer flex-col items-center gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
						onclick={() => chooseProfile(profile.id)}
					>
						<ProfileAvatar
							avatar={profile.avatar}
							class="size-32 text-6xl ring-2 ring-transparent transition group-hover:ring-foreground"
						/>
						<span
							class="max-w-full truncate text-muted-foreground group-hover:text-foreground"
							>{profile.name}</span
						>
					</button>
				</li>
			{/each}
			<li>
				<a
					href="/add-profile"
					class="group flex w-32 flex-col items-center gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
				>
					<span
						class="flex size-32 items-center justify-center rounded-md border-2 border-dashed text-muted-foreground transition group-hover:border-foreground group-hover:text-foreground"
					>
						<PlusIcon class="size-12" aria-hidden="true" />
					</span>
					<span class="text-muted-foreground group-hover:text-foreground"
						>Add profile</span
					>
				</a>
			</li>
		</ul>
	{/if}
</main>
