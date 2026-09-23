/**
 * Type declarations for the side-effect CSS imports in `main.tsx`. esbuild
 * resolves them at bundle time via the `inline-css` plugin in `build.mjs`;
 * TypeScript just needs to accept the imports.
 */
declare module '*.css';
