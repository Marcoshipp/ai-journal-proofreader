import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ExportButtonProps {
    markdown: string;
    filename?: string;
}

export function ExportButton({
    markdown,
    filename = "validation_report.md",
}: ExportButtonProps) {
    const handleExport = () => {
        const blob = new Blob([markdown], { type: "text/markdown" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <Button onClick={handleExport} variant="outline" className="gap-2">
            <Download className="w-4 h-4" />
            Export Report
        </Button>
    );
}
