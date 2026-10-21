<script lang="ts">
	import { page } from '$app/state'

	const NAV_LINKS = [
		{ href: '/', label: 'Discover' },
		{ href: '/songs', label: 'Songs' },
		{ href: '/taste', label: 'Taste' },
	]
</script>

<header class="sticky top-0 z-40 border-b bg-background/80 backdrop-blur">
	<nav
		class="mx-auto flex max-w-7xl items-center gap-6 px-6 py-3"
		aria-label="Main"
	>
		<a href="/" class="mr-auto font-semibold">Music Recs</a>
		{#each NAV_LINKS as link (link.href)}
			{@const isActive = page.url.pathname === link.href}
			<a
				href={link.href}
				class="rounded-sm text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring {isActive
					? 'font-medium text-foreground'
					: 'text-muted-foreground hover:text-foreground'}"
				aria-current={isActive ? 'page' : undefined}>{link.label}</a
			>
		{/each}
	</nav>
</header>
