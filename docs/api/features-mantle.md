# `features/mantle.py`

Ledge search, climb plan, vault path, host mantle replay (`_HOST_MANTLES`), audio/shake/height options. A trace hit is a location, a normal, and a material name. The climb reads the first two through `tracing.pair`, so finding a wall does not abort the vault. `_moving_into_wall` treats speed toward the camera as running in.
