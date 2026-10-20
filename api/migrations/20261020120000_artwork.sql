-- Display metadata. The MusicBrainz columns are NULL when there was no confident match.
ALTER TABLE songs ADD COLUMN thumbnail_url TEXT;
ALTER TABLE songs ADD COLUMN album_art_url TEXT;
ALTER TABLE songs ADD COLUMN album TEXT;
ALTER TABLE songs ADD COLUMN musicbrainz_recording_id TEXT;
ALTER TABLE songs ADD COLUMN musicbrainz_release_group_id TEXT;

UPDATE songs SET thumbnail_url = 'https://img.youtube.com/vi/' || video_id || '/hqdefault.jpg';
