<script lang="ts">
	import ProfileForm from '#lib/components/ProfileForm.svelte'
	import { addProfile, profiles, selectProfile } from '#lib/profiles.svelte.js'
	import { goto } from '$app/navigation'

	const isFirstProfile = $derived(profiles.items.length === 0)
	// The first profile has nothing to go back to.
	const cancelHref = $derived(
		isFirstProfile ? undefined : profiles.activeId === null ? '/profiles' : '/'
	)

	async function createProfile(input: { name: string; avatar: string }) {
		const created = await addProfile(input)
		selectProfile(created.id)
		await goto('/')
	}
</script>

<svelte:head>
	<title>Add profile</title>
</svelte:head>

<main class="mx-auto flex max-w-xl flex-col gap-8 px-6 py-16">
	<div class="flex flex-col gap-2">
		<h1 class="text-3xl font-semibold tracking-tight">
			{isFirstProfile ? 'Create your profile' : 'Add profile'}
		</h1>
		<p class="text-muted-foreground">
			Each profile has its own taste and recommendations.
		</p>
	</div>
	<ProfileForm
		{cancelHref}
		submitLabel={isFirstProfile ? 'Create profile' : 'Add profile'}
		onsubmit={createProfile}
	/>
</main>
