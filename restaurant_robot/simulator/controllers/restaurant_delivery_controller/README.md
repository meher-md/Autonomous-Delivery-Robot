# Webots Controller

This source is the intended direct Webots C++ controller entrypoint. It is not compiled by the root CMake build because Webots include and library paths are installation-specific.

Expected Webots device names for the stock TurtleBot3 Burger model:

- `LDS-01`
- `inertial unit`
- `left wheel motor`
- `right wheel motor`
- `left wheel sensor`
- `right wheel sensor`

If a local Webots release uses different names, update only `WebotsHardware`; the planner, controller, safety, and mission modules should remain unchanged.
