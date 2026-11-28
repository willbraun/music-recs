import {
	createProfile,
	deleteProfile,
	listProfiles,
	setApiProfileId,
	updateProfile,
	type Profile,
	type ProfileInput,
} from '#lib/api.js'
import { stopPlayer } from '#lib/player.svelte.js'
import { cancelCurrentRun, isRunActive, resetRun } from '#lib/run.svelte.js'
import { clearTaste, loadTaste } from '#lib/taste.svelte.js'

export type ProfilesStatus = 'loading' | 'ready' | 'error'

export interface ProfilesState {
	status: ProfilesStatus
	items: Profile[]
	// Null until a profile is picked in this tab.
	activeId: number | null
	error: string | null
	// A switch waiting for the user to confirm cancelling the current run.
	pendingSwitchId: number | null
}

// Per tab, so every app launch starts at the picker and two tabs can use different profiles.
const ACTIVE_PROFILE_KEY = 'music-recs:profile-id'

function readStoredId(): number | null {
	const stored = sessionStorage.getItem(ACTIVE_PROFILE_KEY)
	return stored === null || Number.isNaN(Number(stored)) ? null : Number(stored)
}

export const profiles: ProfilesState = $state({
	status: 'loading',
	items: [],
	activeId: readStoredId(),
	error: null,
	pendingSwitchId: null,
})

setApiProfileId(profiles.activeId)

export function getActiveProfile(): Profile | null {
	return profiles.items.find((item) => item.id === profiles.activeId) ?? null
}

function setActiveId(id: number | null) {
	profiles.activeId = id
	setApiProfileId(id)
	if (id === null) sessionStorage.removeItem(ACTIVE_PROFILE_KEY)
	else sessionStorage.setItem(ACTIVE_PROFILE_KEY, String(id))
}

// Everything loaded for the previous profile is dropped, so nothing of theirs shows for the next.
function resetProfileState() {
	resetRun()
	stopPlayer()
	clearTaste()
}

export async function loadProfiles() {
	profiles.status = 'loading'
	profiles.error = null
	try {
		profiles.items = await listProfiles()
		// The stored profile may have been deleted from another tab or window.
		if (getActiveProfile() === null) setActiveId(null)
		profiles.status = 'ready'
	} catch (error) {
		profiles.error =
			error instanceof Error ? error.message : 'Could not load profiles'
		profiles.status = 'error'
	}
}

export function selectProfile(id: number) {
	if (profiles.activeId === id) return
	resetProfileState()
	setActiveId(id)
	void loadTaste()
}

export async function addProfile(input: ProfileInput): Promise<Profile> {
	const created = await createProfile(input)
	profiles.items.push(created)
	return created
}

export async function saveProfile(
	id: number,
	input: ProfileInput
): Promise<Profile> {
	const saved = await updateProfile(id, input)
	const index = profiles.items.findIndex((item) => item.id === id)
	if (index === -1) profiles.items.push(saved)
	else profiles.items[index] = saved
	return saved
}

export async function removeProfile(id: number) {
	await deleteProfile(id)
	profiles.items = profiles.items.filter((item) => item.id !== id)
	if (profiles.activeId === id) {
		resetProfileState()
		setActiveId(null)
	}
}

// Switches now and returns true, or asks for confirmation first when a run would be lost.
export function requestProfileSwitch(id: number): boolean {
	if (profiles.activeId !== id && isRunActive()) {
		profiles.pendingSwitchId = id
		return false
	}
	selectProfile(id)
	return true
}

export async function confirmProfileSwitch(): Promise<boolean> {
	const id = profiles.pendingSwitchId
	profiles.pendingSwitchId = null
	if (id === null) return false
	await cancelCurrentRun()
	selectProfile(id)
	return true
}

export function cancelProfileSwitch() {
	profiles.pendingSwitchId = null
}
