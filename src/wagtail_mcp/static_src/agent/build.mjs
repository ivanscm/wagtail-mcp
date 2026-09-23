/**
 * Bundle the admin chat to one ESM file:
 * static/wagtail_mcp/js/agent.js (CSS inlined; no bare imports).
 */
import * as esbuild from 'esbuild';
import { mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const outdir = resolve(here, '../../static/wagtail_mcp/js');

await mkdir(outdir, { recursive: true });

/** Options shared by the one-shot build and the watch mode. */
const options = {
  entryPoints: [resolve(here, 'main.tsx')],
  bundle: true,
  format: 'esm',
  jsx: 'automatic',
  minify: true,
  sourcemap: false,
  target: ['es2022'],
  outfile: resolve(outdir, 'agent.js'),
  loader: {
    // CopilotKit's stylesheet transitively pulls in KaTeX's fonts; emit them
    // as data URLs so everything stays inside the one output file.
    '.woff': 'dataurl',
    '.woff2': 'dataurl',
    '.ttf': 'dataurl',
  },
  banner: {
    js: '/* Built from wagtail_mcp/static_src/agent via `npm run build:agent`. Do not edit. */',
  },
  define: {
    // CopilotKit checks NODE_ENV in several places; pin it to production so
    // development-only warnings and the Inspector stay out of the bundle.
    'process.env.NODE_ENV': '"production"',
  },
  logLevel: 'info',
  plugins: [
    {
      name: 'inline-css',
      setup(build) {
        // Inline each stylesheet as a <style> tag. A nested build resolves
        // url() references (KaTeX fonts) to the dataurl loaders below.
        build.onLoad({ filter: /\.css$/ }, async (args) => {
          const result = await esbuild.build({
            entryPoints: [args.path],
            bundle: true,
            minify: true,
            write: false,
            loader: {
              '.woff': 'dataurl',
              '.woff2': 'dataurl',
              '.ttf': 'dataurl',
            },
          });
          const css = result.outputFiles[0].text;
          return {
            contents: `const css = ${JSON.stringify(css)};
const style = document.createElement("style");
style.setAttribute("data-wagtail-mcp-agent", "");
style.textContent = css;
document.head.appendChild(style);
export default css;`,
            loader: 'js',
          };
        });
      },
    },
  ],
};

if (process.argv.includes('--watch')) {
  const ctx = await esbuild.context(options);
  await ctx.watch();
  console.log('watching for changes…');
} else {
  await esbuild.build(options);
}
