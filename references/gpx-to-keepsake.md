# GPX To Keepsake Reference

## Internal Point Schema

Normalize every route format into:

```json
{
  "lat": 28.0,
  "lon": 121.0,
  "ele": 47.0,
  "time": "2025-11-21T23:34:08Z",
  "speed": 1.32
}
```

## Public Share Privacy

For public outputs, avoid exposing:

- exact start and end coordinates,
- informal entrances,
- private addresses,
- unofficial trail shortcuts,
- fragile ecological locations.

Use approximate location labels and cropped route silhouettes instead.

## MVP Output Hierarchy

1. Generate the data asset pack from GPX.
2. Generate a strong 3D trail visual.
3. Adapt the same asset pack into poster, magnet, postcard, and social layouts.

Keep route analysis deterministic. Let the LLM write names, captions, and story copy only after the computed stats exist.
