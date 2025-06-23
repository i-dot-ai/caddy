# Caddy Admin UI


## Getting started

1. Copy `.env.example` to `.env` and update the env vars accordingly
2. Run `npm install` in the frontend directory
3. Run `npm run dev`


## Project Structure

Inside of your Astro project, you'll see the following folders and files:

```text
/
├── public/
├── src/
│   └── pages/
│       └── index.astro
└── package.json
```

Astro looks for `.astro` or `.md` files in the `src/pages/` directory. Each page is exposed as a route based on its file name.

There's nothing special about `src/components/`, but that's where we like to put any Astro/Lit components.

Any static assets, like images, can be placed in the `public/` directory.


## 🧞 Commands

All commands are run from the frontend directory:

| Command                   | Action                                           |
| :------------------------ | :----------------------------------------------- |
| `npm install`             | Installs dependencies                            |
| `npm run dev`             | Starts local dev server at `localhost:4321`      |
| `npm run build`           | Build your production site to `./dist/`          |
| `npm run preview`         | Preview your build locally, before deploying     |
| `npm run tests`           | Run Playwright end-to-end tests                  |
