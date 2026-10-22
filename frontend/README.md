# Frontend scaffold (not the USB Fix Tool desktop UI)

This `frontend/` directory is a separate **Create React App / CRACO starter**. Its current `src/App.js` renders a simple placeholder and calls a demonstration `/api/` endpoint.

It is **not** the desktop USB Fix Tool, not the static marketing website under `usb-fix-tool/website/`, and not a browser-based USB repair implementation.

## Existing commands

From this directory, with compatible Node.js and package dependencies installed:

```bash
yarn install
yarn start
yarn build
yarn test
```

These commands correspond to scripts declared in `package.json`. `REACT_APP_BACKEND_URL` is read by `src/App.js`; without configuration the example API call may fail. No development server, tests or production build were run during the documentation update.

See the [repository overview](../README.md) for the actual Windows desktop utility and its installation instructions.

## License

The repository includes the [MIT License](../LICENSE) for project-owned material. Dependencies and third-party scaffolding retain their own licensing conditions.
