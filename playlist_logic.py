from typing import Dict, List, Optional, Tuple
import random

Song = Dict[str, object]
PlaylistMap = Dict[str, List[Song]]

DEFAULT_PROFILE = {
    "name": "Default",
    "hype_min_energy": 7,
    "chill_max_energy": 3,
    "favorite_genre": "rock",
    "include_mixed": True,
}


def normalize_title(title: str) -> str:
    """Normalize a song title for comparisons."""
    if not isinstance(title, str):
        return ""
    return title.strip().lower()


def normalize_artist(artist: str) -> str:
    """Normalize an artist name for comparisons."""
    if not artist:
        return ""
    return artist.strip().lower()


def normalize_genre(genre: str) -> str:
    """Normalize a genre name for comparisons."""
    if not isinstance(genre, str):
        return ""
    return genre.strip().lower()


def normalize_song(raw: Song) -> Song:
    """Return a normalized song dict with expected keys."""
    title = normalize_title(str(raw.get("title", "")))
    artist = normalize_artist(str(raw.get("artist", "")))
    genre = normalize_genre(str(raw.get("genre", "")))

    # parse energy robustly (allow "7", "7.5", etc.)
    energy_raw = raw.get("energy", 0)
    try:
        energy_val = float(energy_raw)
        energy = int(energy_val) if energy_val.is_integer() else energy_val
    except (TypeError, ValueError):
        energy = 0

    # normalize tags (handle string or list)
    tags = raw.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    normalized_tags = [str(t).strip().lower() for t in tags if t is not None]

    return {
        "title": title,
        "artist": artist,
        "genre": genre,
        "energy": energy,
        "tags": normalized_tags,
    }


def classify_song(song: Song, profile: Dict[str, object]) -> str:
    """Return a mood label given a song and user profile."""
    # normalize fields for case-insensitive matching
    energy = song.get("energy", 0)
    try:
        energy_val = float(energy)
    except (TypeError, ValueError):
        energy_val = 0.0

    genre = str(song.get("genre", "")).lower()
    title = str(song.get("title", "")).lower()

    hype_min_energy = float(profile.get("hype_min_energy", 7))
    chill_max_energy = float(profile.get("chill_max_energy", 3))
    favorite_genre = str(profile.get("favorite_genre", "")).lower()

    hype_keywords = ["rock", "punk", "party"]
    chill_keywords = ["lofi", "ambient", "sleep"]

    is_hype_keyword = any(k in genre for k in hype_keywords)
    is_chill_keyword = any(k in title for k in chill_keywords)

    # Hype: energy >= threshold OR genre matches favorite OR genre contains hype keywords
    if genre == favorite_genre or energy_val >= hype_min_energy or is_hype_keyword:
        return "Hype"
    # Chill: energy <= threshold OR title contains chill keywords
    if energy_val <= chill_max_energy or is_chill_keyword:
        return "Chill"
    # Otherwise Mixed
    return "Mixed"


def build_playlists(songs: List[Song], profile: Dict[str, object]) -> PlaylistMap:
    """Group songs into playlists based on mood and profile."""
    playlists: PlaylistMap = {
        "Hype": [],
        "Chill": [],
        "Mixed": [],
    }

    for song in songs:
        normalized = normalize_song(song)
        mood = classify_song(normalized, profile)
        normalized["mood"] = mood
        playlists[mood].append(normalized)

    return playlists

# Changes: wrap a.get(key, []) and b.get(key, []) with list() to create shallow copies. This prevents the function from accidentally mutating the caller's original playlists.
def merge_playlists(a: PlaylistMap, b: PlaylistMap) -> PlaylistMap:
    """Merge two playlist maps into a new map without mutating inputs."""
    merged: PlaylistMap = {}
    for key in set(list(a.keys()) + list(b.keys())):
        merged[key] = list(a.get(key, []))
        merged[key].extend(list(b.get(key, [])))
    return merged


def _song_key(s: Song) -> Tuple[str, str]:
    """Return normalized (title, artist) key for deduplication."""
    return (
        str(s.get("title", "")).strip().lower(),
        str(s.get("artist", "")).strip().lower(),
    )


def compute_playlist_stats(playlists: PlaylistMap) -> Dict[str, object]:
    """Compute statistics across all playlists."""
    all_songs: List[Song] = []
    for songs in playlists.values():
        all_songs.extend(songs)

    hype = playlists.get("Hype", [])
    chill = playlists.get("Chill", [])
    mixed = playlists.get("Mixed", [])

    # deduplicate by (title, artist)
    unique_map: Dict[Tuple[str, str], Song] = {}
    for s in all_songs:
        k = _song_key(s)
        if k not in unique_map:
            unique_map[k] = s

    total = len(unique_map)
    unique_hype = {_song_key(s) for s in hype}
    hype_count = len(unique_hype)
    hype_ratio = hype_count / total if total > 0 else 0.0

    avg_energy = 0.0
    if unique_map:
        total_energy = sum(song.get("energy", 0) for song in unique_map.values())
        avg_energy = total_energy / len(unique_map)

    unique_songs_list = list(unique_map.values())
    top_artist, top_count = most_common_artist(unique_songs_list)

    return {
        "total_songs": total,
        "hype_count": hype_count,
        "chill_count": len({_song_key(s) for s in chill}),
        "mixed_count": len({_song_key(s) for s in mixed}),
        "hype_ratio": hype_ratio,
        "avg_energy": avg_energy,
        "top_artist": top_artist,
        "top_artist_count": top_count,
    }


def most_common_artist(songs: List[Song]) -> Tuple[str, int]:
    """Return the most common artist and count."""
    counts: Dict[str, int] = {}
    for song in songs:
        artist = str(song.get("artist", ""))
        if not artist:
            continue
        counts[artist] = counts.get(artist, 0) + 1

    if not counts:
        return "", 0

    items = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return items[0]


def search_songs(
    songs: List[Song],
    query: str,
    field: str = "artist",
) -> List[Song]:
    """Return songs matching the query on a given field."""
    if not query:
        return songs

    q = query.lower().strip()
    filtered: List[Song] = []
    seen: set = set()

    for song in songs:
        key = _song_key(song)
        if key in seen:
            continue
        seen.add(key)

        val = song.get(field, "")
        if isinstance(val, list):
            values = [str(v).lower() for v in val]
            if any(q in v for v in values):
                filtered.append(song)
            continue

        value = str(val).lower()
        if q in value:
            filtered.append(song)

    return filtered


def lucky_pick(
    playlists: PlaylistMap,
    mode: str = "any",
) -> Optional[Song]:
    """Pick a song from the playlists according to mode."""
    m = (mode or "any").strip().lower()

    if m == "hype":
        songs = playlists.get("Hype", [])
    elif m == "chill":
        songs = playlists.get("Chill", [])
    else:
        # "any" or unknown mode => combine Hype, Chill, Mixed
        songs = []
        for key in ("Hype", "Chill", "Mixed"):
            songs.extend(playlists.get(key, []))

    return random_choice_or_none(songs)


def random_choice_or_none(songs: List[Song]) -> Optional[Song]:
    """Return a random song from the list or None if empty."""
    if not songs:
        return None
    return random.choice(songs)


def history_summary(history: List[Song]) -> Dict[str, int]:
    """Return a summary of moods seen in the history."""
    counts = {"Hype": 0, "Chill": 0, "Mixed": 0}
    for song in history:
        mood = song.get("mood", "Mixed")
        if mood not in counts:
            counts["Mixed"] += 1
        else:
            counts[mood] += 1
    return counts
