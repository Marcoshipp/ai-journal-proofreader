import { useState, useEffect, useCallback, useRef } from "react";
import { Link } from "react-router-dom";
import { FileUpload } from "@/components/FileUpload";
import { ProgressTracker } from "@/components/ProgressTracker";
import { ReportView } from "@/components/ReportView";
import { ExportButton } from "@/components/ExportButton";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { RotateCcw, FileSearch, Settings } from "lucide-react";
import {
    fetchJournals,
    startValidation,
    subscribeToProgress,
    type Journal,
    type ProgressPayload,
    type ValidationStep,
} from "@/lib/api";

type PageState = "upload" | "processing" | "report";

export default function MainPage() {
    const [pageState, setPageState] = useState<PageState>("upload");
    const [journals, setJournals] = useState<Journal[]>([]);
    const [selectedJournalId, setSelectedJournalId] = useState<string>("");
    const [selectedArticleTypeId, setSelectedArticleTypeId] =
        useState<string>("");
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [steps, setSteps] = useState<ValidationStep[]>([]);
    const [processStatus, setProcessStatus] = useState<
        "processing" | "complete" | "error"
    >("processing");
    const [reportMarkdown, setReportMarkdown] = useState("");
    const [results, setResults] = useState<NonNullable<
        ProgressPayload["results"]
    > | null>(null);
    const [error, setError] = useState<string | null>(null);
    const cleanupRef = useRef<(() => void) | null>(null);

    // Load journals on mount
    useEffect(() => {
        fetchJournals()
            .then((j) => {
                setJournals(j);
                if (j.length > 0) {
                    setSelectedJournalId(j[0].id);
                    if (j[0].article_types && j[0].article_types.length > 0) {
                        setSelectedArticleTypeId(j[0].article_types[0].id);
                    }
                }
            })
            .catch((err) => console.error("Failed to load journals:", err));
    }, []);

    // Update article type selection when journal changes
    useEffect(() => {
        const journal = journals.find((j) => j.id === selectedJournalId);
        if (
            journal &&
            journal.article_types &&
            journal.article_types.length > 0
        ) {
            // Check if current type is valid for new journal, if not, pick the first one
            if (
                !journal.article_types.find(
                    (t) => t.id === selectedArticleTypeId,
                )
            ) {
                setSelectedArticleTypeId(journal.article_types[0].id);
            }
        } else {
            setSelectedArticleTypeId("");
        }
    }, [selectedJournalId, journals]);

    const handleFileSelect = useCallback((file: File) => {
        setSelectedFile(file);
    }, []);

    const handleSubmit = useCallback(async () => {
        if (!selectedFile || !selectedJournalId) return;

        setPageState("processing");
        setSteps([]);
        setProcessStatus("processing");
        setError(null);

        try {
            const jobId = await startValidation(
                selectedFile,
                selectedJournalId,
                selectedArticleTypeId || undefined,
            );

            const cleanup = subscribeToProgress(
                jobId,
                (payload) => {
                    setSteps([...payload.steps]);
                    setProcessStatus(
                        payload.status as "processing" | "complete" | "error",
                    );

                    if (payload.status === "complete") {
                        setReportMarkdown(payload.report_markdown || "");
                        setResults(payload.results || null);
                        setPageState("report");
                    } else if (payload.status === "error") {
                        setError(payload.error || "Unknown error");
                    }
                },
                (errMsg) => {
                    setError(errMsg);
                    setProcessStatus("error");
                },
            );

            cleanupRef.current = cleanup;
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Failed to start validation",
            );
            setProcessStatus("error");
        }
    }, [selectedFile, selectedJournalId, selectedArticleTypeId]);

    const handleReset = useCallback(() => {
        if (cleanupRef.current) {
            cleanupRef.current();
            cleanupRef.current = null;
        }
        setPageState("upload");
        setSelectedFile(null);
        setSteps([]);
        setReportMarkdown("");
        setResults(null);
        setError(null);
        setProcessStatus("processing");
    }, []);

    return (
        <div className="min-h-screen bg-background">
            {/* Header */}
            <header className="border-b border-border/40 bg-card/50 backdrop-blur-sm sticky top-0 z-50">
                <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
                            <FileSearch className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                            <h1 className="text-lg font-semibold tracking-tight">
                                Journal Proofreader
                            </h1>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        {pageState !== "upload" && (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={handleReset}
                                className="gap-2"
                            >
                                <RotateCcw className="w-4 h-4" />
                                New Check
                            </Button>
                        )}
                        <Link to="/settings">
                            <Button
                                variant="ghost"
                                size="icon"
                                className="w-8 h-8"
                            >
                                <Settings className="w-4 h-4" />
                            </Button>
                        </Link>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="max-w-4xl mx-auto px-6 py-8">
                {pageState === "upload" && (
                    <div className="space-y-6 animate-in fade-in duration-500">
                        <div className="text-center space-y-2 mb-8">
                            <h2 className="text-2xl font-bold tracking-tight">
                                期刊稿件格式檢查
                            </h2>
                            <p className="text-muted-foreground">
                                上傳 PDF 並選擇目標期刊，檢查格式合規性
                            </p>
                        </div>

                        {/* Journal and Article Type Selection */}
                        <div className="grid grid-cols-2 gap-4">
                            <Card className="border-slate-200">
                                <CardHeader className="pb-3">
                                    <CardTitle className="text-sm font-bold">
                                        選擇目標期刊
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <Select
                                        value={selectedJournalId}
                                        onValueChange={setSelectedJournalId}
                                    >
                                        <SelectTrigger className="w-full">
                                            <SelectValue placeholder="Select a journal..." />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {journals.map((j) => (
                                                <SelectItem
                                                    key={j.id}
                                                    value={j.id}
                                                >
                                                    {j.name}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </CardContent>
                            </Card>

                            <Card className="border-slate-200">
                                <CardHeader className="pb-3">
                                    <CardTitle className="text-sm font-bold">
                                        選擇文章類型
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <Select
                                        value={selectedArticleTypeId}
                                        onValueChange={setSelectedArticleTypeId}
                                        disabled={
                                            !selectedJournalId ||
                                            journals.find(
                                                (j) =>
                                                    j.id === selectedJournalId,
                                            )?.article_types?.length === 0
                                        }
                                    >
                                        <SelectTrigger className="w-full">
                                            <SelectValue placeholder="Select article type..." />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {journals
                                                .find(
                                                    (j) =>
                                                        j.id ===
                                                        selectedJournalId,
                                                )
                                                ?.article_types?.map((t) => (
                                                    <SelectItem
                                                        key={t.id}
                                                        value={t.id}
                                                    >
                                                        {t.name}
                                                    </SelectItem>
                                                ))}
                                        </SelectContent>
                                    </Select>
                                </CardContent>
                            </Card>
                        </div>

                        {/* File Upload */}
                        <FileUpload onFileSelect={handleFileSelect} />

                        {/* Submit */}
                        <Button
                            className="w-full"
                            size="lg"
                            disabled={
                                !selectedFile ||
                                !selectedJournalId ||
                                !selectedArticleTypeId
                            }
                            onClick={handleSubmit}
                        >
                            開始校對
                        </Button>
                    </div>
                )}

                {pageState === "processing" && (
                    <div className="space-y-6 animate-in fade-in duration-500">
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base">
                                    Validating{" "}
                                    <span className="text-primary">
                                        {selectedFile?.name}
                                    </span>
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <ProgressTracker
                                    steps={steps}
                                    status={processStatus}
                                    error={error || undefined}
                                />
                            </CardContent>
                        </Card>
                    </div>
                )}

                {pageState === "report" && (
                    <div className="space-y-6 animate-in fade-in duration-500">
                        <div className="flex items-center justify-between">
                            <h2 className="text-xl font-bold tracking-tight">
                                Validation Report
                            </h2>
                            <ExportButton markdown={reportMarkdown} />
                        </div>
                        <Separator />
                        {results && (
                            <ReportView
                                markdown={reportMarkdown}
                                results={results}
                            />
                        )}
                    </div>
                )}
            </main>
        </div>
    );
}
