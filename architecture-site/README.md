# CompassX Platform Architecture

Internal architecture site. Page content lives in `content/` as Markdown. The site only renders those files.

```bash
cd architecture-site
npm install
npm run dev
```

Open http://127.0.0.1:4400

When a module is restructured, update `content/modules/<module>.md` in the same change and add a nav entry in `content/nav.json` if the page is new. Agents and developers read the same files.
