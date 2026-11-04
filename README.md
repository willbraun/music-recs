# Music Recs

Music Recs is a local music recommendation tool. It finds music online, analyzes it with local audio models, and recommends songs based on your musical preferences.

## Models

Music Recs uses two models, which are downloaded from Hugging Face and run on your computer:

- [Qwen 2.5 3B Instruct](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct) translates your musical taste into search queries.
- [Music Flamingo 2601](https://huggingface.co/nvidia/music-flamingo-2601-hf) listens to each song clip and decides whether you would like it.

## Licenses

This repository does not include the models and does not grant any rights to them. Each model has its own license:

- Qwen 2.5 3B Instruct: [Qwen Research License](frontend/static/licenses/Qwen-Research-License-Agreement.txt), limited to research or evaluation use.
- Music Flamingo 2601: [NVIDIA OneWay Noncommercial License](frontend/static/licenses/NVIDIA-OneWay-Noncommercial-License_22Mar2022-academic.docx), limited to academic, non-commercial use.

You are responsible for making sure your use follows each model's license.
