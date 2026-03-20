// preload.js – runs in the renderer process with Node access stripped.
// Expose only what the frontend actually needs via contextBridge.

const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
    // Expose the backend base URL so frontend code can reference it
    // without hardcoding, in case the port ever changes.
    backendURL: "http://localhost:8000",
});
