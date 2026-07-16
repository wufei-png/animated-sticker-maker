# Golden workflow input

This directory contains only the small synthetic source input for the golden workflow tests. Tests build all packages, reports, WebP files, GIF files, and previews in temporary directories.

The same input drives two independently packaged scenarios:

- authored keyframes export;
- explicit render-track export.

The test assertions cover semantic properties and invalidation behavior, not byte-for-byte WebP or GIF output.
