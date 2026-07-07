import { useState } from "react";
import Markdown from "react-markdown";
import { Button } from "@/components/ui/button";
import { Download, ChevronDown, ChevronRight, FileText, BookOpen, Tag } from "lucide-react";

type CheckResult = {
    check_name: string;
    status: string;
    messages: string[];
    details: Record<string, unknown>;
};

type FilterType = "ALL" | "SUCCESS" | "FAILURE" | "WARNING" | "INFO";

interface ReportViewProps {
    markdown: string;
    results: CheckResult[];
    paperTitle?: string;
    journalName?: string;
    articleTypeName?: string;
}

const STATUS_CONFIG: Record<string, { label: string; emoji: string; badgeClass: string; rowClass: string }> = {
    SUCCESS: {
        label: "Pass",
        emoji: "✅",
        badgeClass: "bg-green-50 text-green-700 border-green-200 hover:bg-green-50",
        rowClass: "",
    },
    FAILURE: {
        label: "Fail",
        emoji: "❌",
        badgeClass: "bg-red-50 text-red-700 border-red-200 hover:bg-red-50",
        rowClass: "",
    },
    WARNING: {
        label: "Warning",
        emoji: "⚠️",
        badgeClass: "bg-yellow-50 text-yellow-700 border-yellow-200 hover:bg-yellow-50",
        rowClass: "",
    },
    INFO: {
        label: "Info",
        emoji: "ℹ️",
        badgeClass: "bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-50",
        rowClass: "",
    },
};

function getStatus(status: string) {
    return STATUS_CONFIG[status] ?? STATUS_CONFIG["INFO"];
}

function StatusBadge({ status }: { status: string }) {
    const cfg = getStatus(status);
    return (
        <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border ${cfg.badgeClass}`}>
            <span>{cfg.emoji}</span>
            {cfg.label}
        </span>
    );
}

function StatCard({
    count,
    label,
    color,
    emoji,
}: {
    count: number;
    label: string;
    color: string;
    emoji: string;
}) {
    return (
        <div className={`rounded-xl p-5 text-center ${color} border border-border`}>
            <div className="text-3xl font-bold tracking-tight">{count}</div>
            <div className="mt-1 text-xs font-semibold uppercase tracking-widest opacity-70">
                {emoji} {label}
            </div>
        </div>
    );
}

export function ReportView({
    markdown,
    results,
    paperTitle,
    journalName,
    articleTypeName,
}: ReportViewProps) {
    const [activeTab, setActiveTab] = useState<"overview" | "checklist">("overview");
    const [filter, setFilter] = useState<FilterType>("ALL");
    const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

    const successCount = results.filter((r) => r.status === "SUCCESS").length;
    const failureCount = results.filter((r) => r.status === "FAILURE").length;
    const warningCount = results.filter((r) => r.status === "WARNING").length;
    const infoCount = results.filter((r) => r.status === "INFO").length;

    const filteredResults = filter === "ALL" ? results : results.filter((r) => r.status === filter);

    const toggleRow = (i: number) => {
        setExpandedRows((prev) => {
            const next = new Set(prev);
            if (next.has(i)) next.delete(i);
            else next.add(i);
            return next;
        });
    };

    const handleExport = () => {
        const blob = new Blob([markdown], { type: "text/markdown" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "validation_report.md";
        a.click();
        URL.revokeObjectURL(url);
    };

    const FILTERS: { key: FilterType; label: string; count?: number }[] = [
        { key: "ALL", label: "All Items", count: results.length },
        { key: "SUCCESS", label: "Pass", count: successCount },
        { key: "FAILURE", label: "Fail", count: failureCount },
        { key: "WARNING", label: "Warning", count: warningCount },
        { key: "INFO", label: "Info", count: infoCount },
    ];

    return (
        <div className="space-y-4">
            {/* Top nav: tabs + export */}
            <div className="flex items-center justify-between border-b border-border pb-0">
                <div className="flex gap-0">
                    {(["overview", "checklist"] as const).map((tab) => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors capitalize ${
                                activeTab === tab
                                    ? "border-primary text-primary"
                                    : "border-transparent text-muted-foreground hover:text-foreground"
                            }`}
                        >
                            {tab === "overview" ? "Overview" : (
                                <span className="flex items-center gap-1.5">
                                    Compliance Checklist
                                    <span className="bg-muted text-muted-foreground text-xs rounded-full px-1.5 py-0.5 font-medium">
                                        {results.length}
                                    </span>
                                </span>
                            )}
                        </button>
                    ))}
                </div>
                <Button onClick={handleExport} variant="outline" size="sm" className="gap-2 mb-1">
                    <Download className="w-3.5 h-3.5" />
                    Export
                </Button>
            </div>

            {/* OVERVIEW TAB */}
            {activeTab === "overview" && (
                <div className="space-y-5 animate-in fade-in duration-300">
                    {/* Paper info card */}
                    <div className="rounded-xl border border-border bg-card p-6 space-y-4">
                        {paperTitle && (
                            <div>
                                <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-1">
                                    <FileText className="w-3.5 h-3.5" />
                                    Paper Title
                                </div>
                                <p className="text-base font-semibold leading-snug">{paperTitle}</p>
                            </div>
                        )}
                        {journalName && (
                            <div>
                                <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-1">
                                    <BookOpen className="w-3.5 h-3.5" />
                                    Journal Name
                                </div>
                                <p className="text-sm">{journalName}</p>
                            </div>
                        )}
                        {articleTypeName && (
                            <div>
                                <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-1">
                                    <Tag className="w-3.5 h-3.5" />
                                    Article Type
                                </div>
                                <p className="text-sm">{articleTypeName}</p>
                            </div>
                        )}
                    </div>

                    {/* Stat cards */}
                    <div className="grid grid-cols-4 gap-3">
                        <StatCard count={successCount} label="Pass"    color="bg-green-50 text-green-700"  emoji="✅" />
                        <StatCard count={failureCount} label="Fail"    color="bg-red-50 text-red-700"     emoji="❌" />
                        <StatCard count={warningCount} label="Warning" color="bg-yellow-50 text-yellow-700" emoji="⚠️" />
                        <StatCard count={infoCount}    label="Info"    color="bg-slate-100 text-slate-600" emoji="ℹ️" />
                    </div>
                </div>
            )}

            {/* CHECKLIST TAB */}
            {activeTab === "checklist" && (
                <div className="space-y-3 animate-in fade-in duration-300">
                    {/* Filter pills */}
                    <div className="flex items-center gap-2 flex-wrap">
                        {FILTERS.map(({ key, label, count }) => (
                            <button
                                key={key}
                                onClick={() => setFilter(key)}
                                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors border ${
                                    filter === key
                                        ? "bg-primary text-primary-foreground border-primary"
                                        : "bg-background text-muted-foreground border-border hover:bg-muted"
                                }`}
                            >
                                {label}
                                {count !== undefined && (
                                    <span className={`text-xs rounded-full px-1.5 ${filter === key ? "bg-primary-foreground/20 text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
                                        {count}
                                    </span>
                                )}
                            </button>
                        ))}
                        <span className="ml-auto text-sm text-muted-foreground">
                            {filteredResults.length} items
                        </span>
                    </div>

                    {/* Rows */}
                    <div className="rounded-xl border border-border overflow-hidden bg-card">
                        <div className="border-b border-border bg-muted/40 px-5 py-3">
                            <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                                Compliance Checklist
                            </span>
                        </div>
                        {filteredResults.length === 0 && (
                            <div className="py-12 text-center text-muted-foreground text-sm">
                                No items match this filter.
                            </div>
                        )}
                        {filteredResults.map((result, idx) => {
                            const originalIdx = results.indexOf(result);
                            const isExpanded = expandedRows.has(originalIdx);
                            return (
                                <div key={originalIdx} className="border-b border-border last:border-0">
                                    <button
                                        className="w-full flex items-center gap-4 px-5 py-3.5 hover:bg-muted/30 transition-colors text-left"
                                        onClick={() => toggleRow(originalIdx)}
                                    >
                                        <span className="text-xs text-muted-foreground w-5 flex-shrink-0 font-mono">
                                            {idx + 1}
                                        </span>
                                        <span className="flex-1 text-sm font-medium">
                                            {result.check_name}
                                        </span>
                                        <StatusBadge status={result.status} />
                                        {isExpanded
                                            ? <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                                            : <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                                        }
                                    </button>
                                    {isExpanded && (
                                        <div className="px-5 pb-4 pt-1 bg-muted/20 border-t border-border/50">
                                            {result.status === "INFO" ? (
                                                <div className="prose prose-sm dark:prose-invert max-w-none text-muted-foreground">
                                                    {result.messages.map((msg, mi) => (
                                                        <Markdown key={mi}>
                                                            {msg.replace(/^\[(OK|FAILURE|WARNING|INFO|SKIPPED)\]\s*/, "")}
                                                        </Markdown>
                                                    ))}
                                                </div>
                                            ) : (
                                                <ul className="space-y-1.5">
                                                    {result.messages.map((msg, mi) => (
                                                        <li key={mi} className="text-sm text-muted-foreground leading-relaxed flex gap-2">
                                                            <span className="mt-0.5 text-border">›</span>
                                                            <span>{msg.replace(/^\[(OK|FAILURE|WARNING|INFO|SKIPPED)\]\s*/, "")}</span>
                                                        </li>
                                                    ))}
                                                </ul>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}
