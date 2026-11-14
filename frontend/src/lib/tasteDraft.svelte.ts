// Tracks unsaved taste-form edits so the modal and the page share one leave confirmation.
export const tasteDraft: {
	isDirty: boolean
	pendingLeave: (() => void) | null
} = $state({ isDirty: false, pendingLeave: null })

// Runs `leave` now, or after the user confirms when the form has unsaved edits.
export function requestLeave(leave: () => void) {
	if (tasteDraft.isDirty) tasteDraft.pendingLeave = leave
	else leave()
}

export function confirmLeave() {
	const leave = tasteDraft.pendingLeave
	tasteDraft.pendingLeave = null
	tasteDraft.isDirty = false
	leave?.()
}

export function cancelLeave() {
	tasteDraft.pendingLeave = null
}
