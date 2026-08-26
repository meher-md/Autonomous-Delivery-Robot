Found a real bug: odometry blends two angles by direct numeric averaging. When encoder yaw is near +pi and IMU yaw is near -pi, those are almost the same physical angle, but direct averaging produces a big false jump. That explains the sudden yaw jumps and the rotate-only loop. I’m going to patch that angle fusion to use wrapped angular error.


I’m making a small source fix, not touching the layout/world geometry. The change is only in heading fusion: treat IMU yaw as an angular correction around encoder yaw, instead of averaging two wrapped numbers.