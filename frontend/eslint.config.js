import js from '@eslint/js';
import globals from 'globals';
import tseslint from 'typescript-eslint';
import css from '@eslint/css';
import { defineConfig, globalIgnores } from 'eslint/config';
import stylistic from '@stylistic/eslint-plugin';


export default defineConfig([
  { files: ['**/*.{js,mjs,cjs,ts,mts,cts}'], plugins: { js }, extends: ['js/recommended'] },
  { files: ['**/*.{js,mjs,cjs,ts,mts,cts}'], languageOptions: { globals: { ...globals.browser, ...globals.node } } },
  tseslint.configs.recommended,
  { files: ['**/*.css'], plugins: { css }, language: 'css/css', extends: ['css/recommended'] },
  globalIgnores(['dist/*', '.astro/*']),
  stylistic.configs.all,
  {
    rules: {
      '@stylistic/array-element-newline': ['off'],
      '@stylistic/comma-dangle': ['error', 'always-multiline'],
      '@stylistic/dot-location': ['error', 'property'],
      '@stylistic/function-call-argument-newline': ['off'],
      '@stylistic/function-paren-newline': ['off'],
      '@stylistic/indent': ['error', 2],
      '@stylistic/member-delimiter-style': ['error', { multiline: { delimiter: 'comma' } }],
      '@stylistic/multiline-ternary': ['off'],
      '@stylistic/newline-per-chained-call': ['off'],
      '@stylistic/object-curly-spacing': ['error', 'always'],
      '@stylistic/object-property-newline': ['off'],
      '@stylistic/padded-blocks': ['off'],
      '@stylistic/quote-props': ['error', 'as-needed'],
      '@stylistic/quotes': ['error', 'single'],
    },
  },
]);
