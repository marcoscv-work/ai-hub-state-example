# AI Hub: Project State Report

A single-page, cross-source state report for Liferay AI Hub. It combines three live sources:

- **Jira** delivery (product, all projects, matched by "AI Hub" reference)
- **GitHub** engineering (the public fork `liferay-ai-hub/liferay-portal`)
- **Code** map (the `ai-hub` module at `modules/dxp/apps/ai-hub/`)

Styling is built on **Lexicon Vanilla** tokens and components
(`liferay-design/lexicon-vanilla`), vendored into `css/`.

> Figma state is not included: the source link was a Figma *project* (folder) URL, not a
> `/design/` file with a node id, so it could not be captured. See the report's Figma section
> for how to add it.

## Structure

```
.
├── index.html          # the report
├── css/
│   ├── tokens.css      # Lexicon Vanilla design tokens (vendored)
│   ├── components.css  # Lexicon Vanilla components (vendored)
│   └── report.css      # report-specific layout, built on the tokens
├── .nojekyll           # serve files as-is on GitHub Pages
└── README.md
```

## Deploy to GitHub Pages

This repo publishes from the root of the `main` branch.

```bash
# from the folder that contains index.html
git init
git add .
git commit -m "AI Hub state report"
git branch -M main
git remote add origin https://github.com/marcoscv-work/ai-hub-state-example.git
git push -u origin main
```

Then enable Pages: repository **Settings → Pages → Build and deployment → Source: Deploy from a
branch → Branch: `main` / `/ (root)`**. The site will be served at
`https://marcoscv-work.github.io/ai-hub-state-example/`.

If the repo already has commits, replace the first four commands with a normal
`git add . && git commit && git push`.

## Regenerating

The numbers are a point-in-time snapshot (1 July 2026). Jira counts are floor values from a
text-matched set and include some tangential items. Re-run the analysis to refresh.
