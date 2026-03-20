const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

const PORT = 8000;
let backendProcess = null;
let mainWindow = null;

// ---------------------------------------------------------------------------
// Locate the backend executable (works both in dev and when packaged)
// ---------------------------------------------------------------------------
function getBackendPath() {
    if (app.isPackaged) {
        // electron-builder copies extraResources into process.resourcesPath
        const exe = process.platform === "win32" ? "backend.exe" : "backend";
        return path.join(process.resourcesPath, "backend", exe);
    }
    // Dev: run via uv from the backend source folder
    return null;
}

// ---------------------------------------------------------------------------
// Start the Python backend
// ---------------------------------------------------------------------------
function startBackend() {
    const backendExe = getBackendPath();

    if (backendExe) {
        // Packaged mode – launch the PyInstaller binary
        if (!fs.existsSync(backendExe)) {
            dialog.showErrorBox(
                "Backend not found",
                `Expected backend at:\n${backendExe}`,
            );
            app.quit();
            return;
        }
        backendProcess = spawn(backendExe, [], {
            cwd: path.dirname(backendExe),
            stdio: "ignore",
        });
    } else {
        // Dev mode – use uv run python main.py
        const backendDir = path.join(__dirname, "..", "backend");
        backendProcess = spawn("uv", ["run", "python", "main.py"], {
            cwd: backendDir,
            stdio: "inherit", // shows backend logs in terminal during dev
            shell: process.platform === "win32", // needed on Windows for uv shim
        });
    }

    backendProcess.on("error", (err) => {
        dialog.showErrorBox("Backend error", err.message);
    });

    backendProcess.on("exit", (code) => {
        if (code !== 0 && code !== null) {
            console.error(`Backend exited with code ${code}`);
        }
    });
}

// ---------------------------------------------------------------------------
// Wait until the backend is accepting connections, then open the window
// ---------------------------------------------------------------------------
function waitForBackend(retries = 30, intervalMs = 500) {
    const net = require("net");
    return new Promise((resolve, reject) => {
        let attempts = 0;
        const check = () => {
            const sock = new net.Socket();
            sock.once("connect", () => {
                sock.destroy();
                resolve();
            })
                .once("error", () => {
                    sock.destroy();
                    attempts++;
                    if (attempts >= retries) {
                        reject(new Error("Backend did not start in time"));
                    } else {
                        setTimeout(check, intervalMs);
                    }
                })
                .connect(PORT, "127.0.0.1");
        };
        check();
    });
}

// ---------------------------------------------------------------------------
// Create the main browser window
// ---------------------------------------------------------------------------
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1280,
        height: 800,
        title: "AI Journal Proofreader",
        webPreferences: {
            preload: path.join(__dirname, "preload.js"),
            contextIsolation: true,
            nodeIntegration: false,
        },
    });

    if (app.isPackaged) {
        // Load the built React static files
        mainWindow.loadFile(
            path.join(__dirname, "..", "frontend", "dist", "index.html"),
        );
    } else {
        // Dev: load Vite dev server (run `pnpm dev` separately in frontend/)
        mainWindow.loadURL("http://localhost:5173");
        mainWindow.webContents.openDevTools();
    }

    mainWindow.on("closed", () => {
        mainWindow = null;
    });
}

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------
app.whenReady().then(async () => {
    startBackend();
    try {
        await waitForBackend();
        createWindow();
    } catch (err) {
        dialog.showErrorBox("Startup failed", err.message);
        app.quit();
    }
});

app.on("window-all-closed", () => {
    if (backendProcess) {
        backendProcess.kill();
        backendProcess = null;
    }
    // On macOS it's conventional to keep the app running until Cmd+Q
    if (process.platform !== "darwin") {
        app.quit();
    }
});

app.on("activate", () => {
    if (mainWindow === null) createWindow();
});

app.on("before-quit", () => {
    if (backendProcess) {
        backendProcess.kill();
        backendProcess = null;
    }
});
