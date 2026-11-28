<script lang="ts">
	import ProfileForm from '#lib/components/ProfileForm.svelte'
	import { Button } from '#lib/components/ui/button/index.js'
	import { profiles, removeProfile, saveProfile } from '#lib/profiles.svelte.js'
	import { goto } from '$app/navigation'
	import { page } from '$app/state'
	import { toast } from 'svelte-sonner'

	const profile = $derived(
		profiles.items.find((item) => item.id === Number(page.params.id))
	)

	async function updateProfile(input: { name: string; avatar: string }) {
		if (!profile) return
		await saveProfile(profile.id, input)
		toast.success('Profile saved')
		await goto('/')
	}

	async function deleteProfile() {
		if (!profile) return
		await removeProfile(profile.id)
		await goto(profiles.items.length > 0 ? '/profiles' : '/add-profile')
	}
</script>

<svelte:head>
	<title>Edit profile</title>
</svelte:head>

<main class="mx-auto flex max-w-xl flex-col gap-8 px-6 py-16">
	<h1 class="text-3xl font-semibold tracking-tight">Edit profile</h1>
	{#if profile}
		{#key profile.id}
			<ProfileForm
				{profile}
				cancelHref="/"
				onsubmit={updateProfile}
				ondelete={deleteProfile}
			/>
		{/key}
	{:else}
		<div class="flex flex-col items-start gap-3">
			<p class="text-muted-foreground">This profile does not exist.</p>
			<Button href="/profiles" variant="outline">Choose a profile</Button>
		</div>
	{/if}
</main>
