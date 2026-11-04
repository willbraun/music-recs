export interface ModelLicense {
	name: string
	// In-app route that renders the license text.
	path: string
	// The original file: viewed in the browser, or downloaded when the browser cannot show it.
	original: { url: string; action: 'view' | 'download' }
	// Terms that come from how the model was trained, beyond its own license.
	note?: string
}

export interface ModelInfo {
	id: string
	name: string
	url: string
	purpose: string
	license: ModelLicense
}

// Keep ids in sync with MODEL_IDS in api/model_download.py. Licenses are from each model card.
export const MODELS: ModelInfo[] = [
	{
		id: 'Qwen/Qwen2.5-3B-Instruct',
		name: 'Qwen 2.5 3B Instruct',
		url: 'https://huggingface.co/Qwen/Qwen2.5-3B-Instruct',
		purpose:
			'Translates your taste into search queries for artists to look up.',
		license: {
			name: 'Qwen Research License',
			path: '/license/qwen',
			original: {
				url: '/licenses/Qwen-Research-License-Agreement.txt',
				action: 'view',
			},
			note: 'Licensed for research or evaluation only. Do not use this app or its output commercially.',
		},
	},
	{
		id: 'nvidia/music-flamingo-2601-hf',
		name: 'Music Flamingo 2601',
		url: 'https://huggingface.co/nvidia/music-flamingo-2601-hf',
		purpose:
			'Listens to a clip of each song and decides whether you would like it, with a confidence score.',
		license: {
			name: 'NVIDIA OneWay Noncommercial License',
			path: '/license/nvidia',
			original: {
				url: '/licenses/NVIDIA-OneWay-Noncommercial-License_22Mar2022-academic.docx',
				action: 'download',
			},
			note: 'Licensed for academic, non-commercial use only. Use this model only if your use is academic, such as research or study. Otherwise, check the license yourself before using this app.',
		},
	},
]

// A model the list does not know falls back to its id and its Hugging Face page.
export function findModel(id: string): Pick<ModelInfo, 'id' | 'name' | 'url'> {
	return (
		MODELS.find((model) => model.id === id) ?? {
			id,
			name: id,
			url: `https://huggingface.co/${id}`,
		}
	)
}
