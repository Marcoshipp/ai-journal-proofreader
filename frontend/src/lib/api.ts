const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";

// ── Config ───────────────────────────────────────────────────────

export interface ParamSchema {
    key: string;
    label: string;
    type: "string_list" | "url";
    hint?: string;
}

export interface CheckSection {
    key: string;
    display_name: string;
    general_description?: string;
    params_schema?: ParamSchema[];
}

export interface Rule {
    type: "general" | "custom";
    instruction?: string;
    enabled?: boolean; // undefined / true = enabled, false = disabled
    params?: Record<string, unknown>; // optional params for parameterised or custom checks
}

export interface ArticleType {
    id: string;
    name: string;
    rules: Record<string, Rule>;
}

export interface Journal {
    id: string;
    name: string;
    article_types: ArticleType[];
}

export interface Config {
    check_sections: CheckSection[];
    journals: Journal[];
}

export async function fetchConfig(): Promise<Config> {
    const res = await fetch(`${API_BASE}/config`);
    if (!res.ok) throw new Error("Failed to fetch config");
    return res.json();
}

export interface GlobalSettings {
    api_key: string;
}

export async function fetchGlobalSettings(): Promise<GlobalSettings> {
    const res = await fetch(`${API_BASE}/config/settings`);
    if (!res.ok) throw new Error("Failed to fetch settings");
    return res.json();
}

export async function updateGlobalSettings(payload: { api_key?: string }): Promise<void> {
    const res = await fetch(`${API_BASE}/config/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Failed to update settings");
}

export async function fetchJournals(): Promise<Journal[]> {
    const res = await fetch(`${API_BASE}/config/journals`);
    if (!res.ok) throw new Error("Failed to fetch journals");
    return res.json();
}

export async function createJournal(name: string): Promise<Journal> {
    const res = await fetch(`${API_BASE}/config/journals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
    });
    if (!res.ok) throw new Error("Failed to create journal");
    return res.json();
}

export async function deleteJournal(journalId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/config/journals/${journalId}`, {
        method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete journal");
}

export async function createArticleType(
    journalId: string,
    name: string,
): Promise<ArticleType> {
    const res = await fetch(
        `${API_BASE}/config/journals/${journalId}/article-types`,
        {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name }),
        },
    );
    if (!res.ok) throw new Error("Failed to create article type");
    return res.json();
}

export async function deleteArticleType(
    journalId: string,
    typeId: string,
): Promise<void> {
    const res = await fetch(
        `${API_BASE}/config/journals/${journalId}/article-types/${typeId}`,
        {
            method: "DELETE",
        },
    );
    if (!res.ok) throw new Error("Failed to delete article type");
}

export async function createCheckSection(payload: {
    name: string;
    description?: string;
    instruction: string;
    context_fields: string[];
    target_journal_id: string;
    target_article_type_id: string;
}): Promise<{ section: CheckSection; rule: Rule }> {
    const res = await fetch(`${API_BASE}/config/check-sections`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Failed to create check section");
    return res.json();
}

export async function updateRule(
    journalId: string,
    typeId: string,
    sectionKey: string,
    rule: Rule,
): Promise<Rule> {
    const res = await fetch(
        `${API_BASE}/config/journals/${journalId}/article-types/${typeId}/rules/${sectionKey}`,
        {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(rule),
        },
    );
    if (!res.ok) throw new Error("Failed to update rule");
    return res.json();
}

export async function toggleCheckEnabled(
    journalId: string,
    typeId: string,
    sectionKey: string,
    currentRule: Rule,
    enabled: boolean,
): Promise<Rule> {
    return updateRule(journalId, typeId, sectionKey, {
        ...currentRule,
        enabled,
    });
}

// ── Validation ───────────────────────────────────────────────────

export interface ValidationStep {
    key: string;
    status: "running" | "done";
    label: string;
    result?: {
        check_name: string;
        status: string;
        messages: string[];
        details: Record<string, unknown>;
    };
}

export interface ProgressPayload {
    status: "processing" | "complete" | "error";
    steps: ValidationStep[];
    report_markdown?: string;
    metadata?: Record<string, unknown>;
    results?: Array<{
        check_name: string;
        status: string;
        messages: string[];
        details: Record<string, unknown>;
    }>;
    error?: string;
}

export async function startValidation(
    file: File,
    journalId: string,
    articleTypeId?: string,
): Promise<string> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("journal_id", journalId);
    if (articleTypeId) {
        formData.append("article_type_id", articleTypeId);
    }

    const res = await fetch(`${API_BASE}/validate`, {
        method: "POST",
        body: formData,
    });
    if (!res.ok) {
        const detail = await res.text();
        throw new Error(`Validation failed: ${detail}`);
    }
    const data = await res.json();
    return data.job_id;
}

export function subscribeToProgress(
    jobId: string,
    onUpdate: (payload: ProgressPayload) => void,
    onError: (error: string) => void,
): () => void {
    const eventSource = new EventSource(
        `${API_BASE}/validate/${jobId}/progress`,
    );

    eventSource.onmessage = (event) => {
        try {
            const payload: ProgressPayload = JSON.parse(event.data);
            onUpdate(payload);

            if (payload.status === "complete" || payload.status === "error") {
                eventSource.close();
            }
        } catch {
            onError("Failed to parse progress update");
            eventSource.close();
        }
    };

    eventSource.onerror = () => {
        onError("Connection to server lost");
        eventSource.close();
    };

    // Return cleanup function
    return () => eventSource.close();
}
