import Markdown from "react-markdown";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";

interface ReportViewProps {
    markdown: string;
    results: Array<{
        check_name: string;
        status: string;
        messages: string[];
        details: Record<string, unknown>;
    }>;
}

export function ReportView({ markdown, results }: ReportViewProps) {
    const successCount = results.filter((r) => r.status === "SUCCESS").length;
    const warningCount = results.filter((r) => r.status === "WARNING").length;
    const failureCount = results.filter((r) => r.status === "FAILURE").length;

    return (
        <div className="space-y-4">
            {/* Summary badges */}
            <div className="flex items-center gap-2 flex-wrap">
                <Badge
                    variant="outline"
                    className="border-green-500/40 text-green-500 bg-green-500/10"
                >
                    ✅ {successCount} passed
                </Badge>
                {warningCount > 0 && (
                    <Badge
                        variant="outline"
                        className="border-yellow-500/40 text-yellow-500 bg-yellow-500/10"
                    >
                        ⚠️ {warningCount} warnings
                    </Badge>
                )}
                {failureCount > 0 && (
                    <Badge
                        variant="outline"
                        className="border-red-500/40 text-red-500 bg-red-500/10"
                    >
                        ❌ {failureCount} failed
                    </Badge>
                )}
            </div>

            {/* Markdown report */}
            <ScrollArea className="h-[700px] rounded-lg border border-border bg-card p-6">
                <article className="prose prose-sm dark:prose-invert max-w-none">
                    <Markdown>{markdown}</Markdown>
                </article>
            </ScrollArea>
        </div>
    );
}
