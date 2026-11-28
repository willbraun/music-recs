<script lang="ts">
	import { page } from '$app/state'
	import { Button } from '#lib/components/ui/button/index.js'
	import * as DropdownMenu from '#lib/components/ui/dropdown-menu/index.js'
	import {
		getActiveProfile,
		profiles,
		requestProfileSwitch,
	} from '#lib/profiles.svelte.js'
	import { RELEASES_URL, update } from '#lib/update.svelte.js'
	import { goto } from '$app/navigation'
	import ChevronDownIcon from '@lucide/svelte/icons/chevron-down'
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link'
	import PencilIcon from '@lucide/svelte/icons/pencil'
	import PlusIcon from '@lucide/svelte/icons/plus'
	import MusicRecs from './icons/logos/MusicRecs.svelte'
	import ProfileAvatar from './ProfileAvatar.svelte'

	const NAV_LINKS = [
		{ href: '/', label: 'Discover' },
		{ href: '/songs', label: 'Songs' },
		{ href: '/taste', label: 'Taste' },
		{ href: '/models', label: 'Models' },
		{ href: '/about', label: 'About' },
	]

	const activeProfile = $derived(getActiveProfile())
	const otherProfiles = $derived(
		profiles.items.filter((profile) => profile.id !== activeProfile?.id)
	)

	function switchProfile(id: number) {
		if (requestProfileSwitch(id)) void goto('/')
	}
</script>

<header class="sticky top-0 z-40 border-b bg-background/80 backdrop-blur">
	<nav
		class="mx-auto flex max-w-7xl items-center gap-2 px-6 py-3"
		aria-label="Main"
	>
		<a href="/" class="mr-6 flex items-center gap-4 font-semibold">
			<MusicRecs />
			<p>Music Recs</p>
		</a>
		{#each NAV_LINKS as link (link.href)}
			{@const isActive = page.url.pathname === link.href}
			<a
				href={link.href}
				class="rounded-full px-3 py-1.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring {isActive
					? 'bg-muted font-medium text-foreground'
					: 'text-muted-foreground hover:text-foreground'}"
				aria-current={isActive ? 'page' : undefined}>{link.label}</a
			>
		{/each}

		<div class="ml-auto flex items-center gap-4">
			{#if update.latestVersion}
				<Button
					href={RELEASES_URL}
					target="_blank"
					rel="noopener noreferrer"
					size="sm"
					title="Version {update.latestVersion} is available"
				>
					New Version Available
					<ExternalLinkIcon aria-hidden="true" />
				</Button>
			{/if}
			{#if activeProfile}
				<DropdownMenu.Root>
					<DropdownMenu.Trigger
						class="group flex cursor-pointer items-center gap-2 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
						aria-label="Profile menu, {activeProfile.name}"
					>
						<ProfileAvatar
							avatar={activeProfile.avatar}
							class="size-9 text-xl"
						/>
						<ChevronDownIcon
							class="size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-180"
							aria-hidden="true"
						/>
					</DropdownMenu.Trigger>
					<DropdownMenu.Content align="end" class="w-56">
						{#each otherProfiles as profile (profile.id)}
							<DropdownMenu.Item
								class="gap-3 py-2"
								onSelect={() => switchProfile(profile.id)}
							>
								<ProfileAvatar avatar={profile.avatar} class="size-8 text-lg" />
								<span class="truncate">{profile.name}</span>
							</DropdownMenu.Item>
						{/each}
						{#if otherProfiles.length > 0}
							<DropdownMenu.Separator />
						{/if}
						<DropdownMenu.Item class="py-2">
							{#snippet child({ props })}
								<a href="/profile/{activeProfile.id}" {...props}>
									<PencilIcon aria-hidden="true" />
									Manage profile
								</a>
							{/snippet}
						</DropdownMenu.Item>
						<DropdownMenu.Item class="py-2">
							{#snippet child({ props })}
								<a href="/add-profile" {...props}>
									<PlusIcon aria-hidden="true" />
									Add profile
								</a>
							{/snippet}
						</DropdownMenu.Item>
					</DropdownMenu.Content>
				</DropdownMenu.Root>
			{/if}
		</div>
	</nav>
</header>
