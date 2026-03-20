import { BrowserRouter, Routes, Route } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import MainPage from "@/pages/MainPage";
import SettingsPage from "@/pages/SettingsPage";
import "./index.css";

function App() {
    return (
        <div className="light">
            <TooltipProvider>
                <BrowserRouter>
                    <Routes>
                        <Route path="/" element={<MainPage />} />
                        <Route path="/settings" element={<SettingsPage />} />
                    </Routes>
                </BrowserRouter>
            </TooltipProvider>
            <Toaster position="top-center" richColors />
        </div>
    );
}

export default App;
