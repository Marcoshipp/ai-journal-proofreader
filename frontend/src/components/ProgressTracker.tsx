import type { ValidationStep } from "@/lib/api";
import { CheckCircle2, Loader2, Circle } from "lucide-react";

interface ProgressTrackerProps {
    steps: ValidationStep[];
    status: "processing" | "complete" | "error";
    error?: string;
}

export function ProgressTracker({
    steps,
    status,
    error,
}: ProgressTrackerProps) {
    return (
        <div className="space-y-3">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                Processing Pipeline
            </h3>

            <div className="space-y-2">
                {steps.map((step, idx) => (
                    <div
                        key={idx}
                        className="flex items-center gap-3 py-1.5 transition-all duration-300"
                    >
                        {step.status === "done" ? (
                            <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
                        ) : step.status === "running" ? (
                            <Loader2 className="w-4 h-4 text-primary animate-spin shrink-0" />
                        ) : (
                            <Circle className="w-4 h-4 text-muted-foreground/40 shrink-0" />
                        )}
                        <span
                            className={`text-sm ${
                                step.status === "done"
                                    ? "text-muted-foreground"
                                    : step.status === "running"
                                      ? "text-foreground font-medium"
                                      : "text-muted-foreground/60"
                            }`}
                        >
                            {step.label}
                        </span>
                        {step.status === "done" && step.result && (
                            <StatusDot status={step.result.status} />
                        )}
                    </div>
                ))}
            </div>

            {status === "error" && error && (
                <div className="mt-3 p-3 bg-destructive/10 border border-destructive/30 rounded-lg">
                    <p className="text-destructive text-sm">{error}</p>
                </div>
            )}
        </div>
    );
}

function StatusDot({ status }: { status: string }) {
    const color =
        status === "SUCCESS"
            ? "bg-green-500"
            : status === "WARNING"
              ? "bg-yellow-500"
              : status === "FAILURE"
                ? "bg-red-500"
                : "bg-blue-500";

    return (
        <span className={`w-2 h-2 rounded-full ${color} shrink-0 ml-auto`} />
    );
}
