import numpy as np

EARTH_RADIUS_MILES = 3958.8


def unit_vectors(lat, lon):
    lat_r, lon_r = np.radians(lat), np.radians(lon)
    cos_lat = np.cos(lat_r)
    return np.column_stack((cos_lat * np.cos(lon_r), cos_lat * np.sin(lon_r), np.sin(lat_r)))


def chord_to_miles(chord):
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.clip(chord / 2, 0, 1))


def miles_to_chord(miles):
    return 2 * np.sin(miles / (2 * EARTH_RADIUS_MILES))


def segment_lengths(lat, lon):
    lat_r, lon_r = np.radians(lat), np.radians(lon)
    dlat, dlon = np.diff(lat_r), np.diff(lon_r)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat_r[:-1]) * np.cos(lat_r[1:]) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def densify(lat, lon, max_step_miles):
    # returns lat, lon, cumulative miles
    lengths = segment_lengths(lat, lon)
    pieces = np.maximum(1, np.ceil(lengths / max_step_miles).astype(int))
    starts = np.repeat(np.arange(len(lengths)), pieces)
    offsets = np.concatenate([np.arange(n) / n for n in pieces]) if len(pieces) else np.array([])

    out_lat = np.append(lat[starts] + (lat[starts + 1] - lat[starts]) * offsets, lat[-1])
    out_lon = np.append(lon[starts] + (lon[starts + 1] - lon[starts]) * offsets, lon[-1])
    cumulative = np.concatenate(([0.0], np.cumsum(np.repeat(lengths / pieces, pieces))))
    return out_lat, out_lon, cumulative


def simplify(points, tolerance):
    # Ramer-Douglas-Peucker
    count = len(points)
    if count < 3:
        return points
    keep = np.zeros(count, dtype=bool)
    keep[[0, -1]] = True
    stack = [(0, count - 1)]
    while stack:
        first, last = stack.pop()
        if last - first < 2:
            continue
        start, end = points[first], points[last]
        inner = points[first + 1:last]
        direction = end - start
        norm = np.hypot(*direction)
        if norm == 0:
            distances = np.hypot(*(inner - start).T)
        else:
            distances = np.abs(direction[0] * (inner[:, 1] - start[1])
                               - direction[1] * (inner[:, 0] - start[0])) / norm
        index = int(np.argmax(distances))
        if distances[index] > tolerance:
            split = first + 1 + index
            keep[split] = True
            stack.append((first, split))
            stack.append((split, last))
    return points[keep]
