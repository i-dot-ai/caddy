import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import css from "@eslint/css";
import { defineConfig, globalIgnores } from "eslint/config";
import stylistic from '@stylistic/eslint-plugin';


export default defineConfig([
  { files: ["**/*.{js,mjs,cjs,ts,mts,cts}"], plugins: { js }, extends: ["js/recommended"] },
  { files: ["**/*.{js,mjs,cjs,ts,mts,cts}"], languageOptions: { globals: {...globals.browser, ...globals.node} } },
  tseslint.configs.recommended,
  { files: ["**/*.css"], plugins: { css }, language: "css/css", extends: ["css/recommended"] },
  globalIgnores(["dist/*", ".astro/*"]),
  {
    plugins: {
      '@stylistic': stylistic
    },
    rules: {
      '@stylistic/semi': 'error'
    }
  }
]);
