import { useCallback, useState } from "react";
import { Upload, FileText } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface FileUploadProps {
    onFileSelect: (file: File) => void;
    disabled?: boolean;
}

export function FileUpload({ onFileSelect, disabled }: FileUploadProps) {
    const [dragActive, setDragActive] = useState(false);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);

    const handleDrag = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            e.stopPropagation();
            if (disabled) return;
            if (e.type === "dragenter" || e.type === "dragover") {
                setDragActive(true);
            } else if (e.type === "dragleave") {
                setDragActive(false);
            }
        },
        [disabled],
    );

    const handleDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            e.stopPropagation();
            setDragActive(false);
            if (disabled) return;

            const file = e.dataTransfer.files?.[0];
            if (file && file.type === "application/pdf") {
                setSelectedFile(file);
                onFileSelect(file);
            }
        },
        [disabled, onFileSelect],
    );

    const handleChange = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            const file = e.target.files?.[0];
            if (file) {
                setSelectedFile(file);
                onFileSelect(file);
            }
        },
        [onFileSelect],
    );

    return (
        <Card
            className={`border-2 border-dashed transition-all duration-200 cursor-pointer ${
                dragActive
                    ? "border-primary bg-primary/5 scale-[1.01]"
                    : selectedFile
                      ? "border-green-500/50 bg-green-500/5"
                      : "border-muted-foreground/25 hover:border-muted-foreground/50"
            } ${disabled ? "opacity-50 pointer-events-none" : ""}`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
        >
            <CardContent className="flex flex-col items-center justify-center py-12 gap-3">
                <label
                    htmlFor="pdf-upload"
                    className="flex flex-col items-center gap-3 cursor-pointer w-full"
                >
                    {selectedFile ? (
                        <>
                            <div className="w-14 h-14 rounded-xl bg-green-500/10 flex items-center justify-center">
                                <FileText className="w-7 h-7 text-green-500" />
                            </div>
                            <div className="text-center">
                                <p className="text-sm font-medium">
                                    {selectedFile.name}
                                </p>
                                <p className="text-xs text-muted-foreground mt-1">
                                    {(selectedFile.size / 1024).toFixed(1)} KB —
                                    Click or drag to replace
                                </p>
                            </div>
                        </>
                    ) : (
                        <>
                            <div className="w-14 h-14 rounded-xl bg-primary/10 flex items-center justify-center">
                                <Upload className="w-7 h-7 text-primary" />
                            </div>
                            <div className="text-center">
                                <p className="text-sm font-medium">
                                    Drop your PDF here
                                </p>
                                <p className="text-xs text-muted-foreground mt-1">
                                    or click to browse
                                </p>
                            </div>
                        </>
                    )}
                    <input
                        id="pdf-upload"
                        type="file"
                        accept=".pdf"
                        className="hidden"
                        onChange={handleChange}
                        disabled={disabled}
                    />
                </label>
            </CardContent>
        </Card>
    );
}
