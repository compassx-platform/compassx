import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";
import federation from '@originjs/vite-plugin-federation';
import { nodePolyfills } from 'vite-plugin-node-polyfills';
import pkg from "./package.json";

/**
 * Patches the federation expose chunk post-build:
 * replaces `reactExports` (local bundled react CJS) with the singleton
 * react obtained via `importShared('react')`.
 *
 * Required because @originjs/vite-plugin-federation only rewrites ESM
 * `import React from 'react'` → `importShared`, but CJS-wrapped deps
 * (TipTap) get rolled up using a local `reactExports` variable instead.
 */
function patchExposeChunkReact(): Plugin {
  return {
    name: 'patch-expose-chunk-react',
    apply: 'build',
    enforce: 'post',
    generateBundle(_opts, bundle) {
      for (const [fileName, chunk] of Object.entries(bundle)) {
        if (
          chunk.type !== 'chunk' ||
          !fileName.includes('__federation_expose_App')
        ) continue;

        let code = chunk.code;

        // Find the line that imports reactExports from the local react chunk
        // e.g.: import { ..., r as reactExports, ... } from './index-Xxxx.js';
        const importLineMatch = code.match(
          /import \{[^}]*\br as reactExports\b[^}]*\} from '\.\/index-[^']+\.js';/
        );
        if (!importLineMatch) continue;

        // Strip reactExports from that import (keep other named exports)
        let patched = code.replace(
          /,\s*r as reactExports\b/g,
          ''
        ).replace(
          /\br as reactExports\s*,/g,
          ''
        ).replace(
          /\br as reactExports\b/g,
          ''
        );

        // After the importShared line for react, re-alias reactExports to the
        // actual shared React binding emitted for this chunk.
        patched = patched.replace(
          /(const (React\$\w+) = await importShared\('react'\);)/,
          `$1\nconst reactExports = $2;`
        );

        chunk.code = patched;
        console.log(`[patch-expose-chunk-react] patched ${fileName}`);
      }
    },
  };
}

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(process.env.VITE_APP_VERSION || pkg.version || "0.4.0"),
  },
  plugins: [
    nodePolyfills({ include: ['buffer', 'stream', 'util'] }),
    react(),
    federation({
      name: 'compassxApp',
      filename: 'remoteEntry.js',
      // Dummy remote: forces builderInfo.isHost=true so plugin rewrites
      // ESM shared imports to importShared() calls.
      remotes: {
        _noop: 'noop@data:text/javascript,export const get=()=>{};export const init=()=>{};',
      },
      exposes: {
        './App': './src/App'
      },
      shared: {
        react: { singleton: true, requiredVersion: false },
        'react-dom': { singleton: true, requiredVersion: false },
        axios: { singleton: true },
        'lucide-react': {},
        '@tanstack/react-query': { singleton: true, requiredVersion: false },
      } as any,
    }),
    patchExposeChunkReact(),
  ],
  css: {
    postcss: "./postcss.config.js",
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      lib: path.resolve(__dirname, "../lib"),
    },
    dedupe: [
      "react",
      "react-dom",
      "@codemirror/state",
      "@codemirror/view",
      "@codemirror/language",
      "@codemirror/commands",
      "@codemirror/lang-python",
      "@lezer/highlight"
    ],
  },
  optimizeDeps: {
    include: [
      "@codemirror/state",
      "@codemirror/view",
      "@codemirror/language",
      "@codemirror/commands",
      "@codemirror/lang-python",
      "@lezer/highlight"
    ],
  },
  build: {
    target: "esnext",
    minify: false,
    commonjsOptions: {
      transformMixedEsModules: true,
    },
    rollupOptions: {
      output: {
        manualChunks: {
          "ui-vendor": [],
        },
      },
    },
    cssCodeSplit: false,
    sourcemap: false,
    chunkSizeWarningLimit: 3000,
  },
  server: {
    proxy: {
      // Proxy Jupyter kernel WebSocket and REST traffic through the backend proxy.
      // Must come before the generic /api rule so it takes priority.
      "/api/v1/notebook/jupyter/api/kernels": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
      // Workspace-scoped API: /w/:slug/api/* → backend
      "^/w/[^/]+/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
    },
    port: 5173,
    host: true,
  },
});
