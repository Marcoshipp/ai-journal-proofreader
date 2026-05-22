import { useState, useEffect, useCallback } from "react";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    AlertDialog,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
    Save,
    RotateCcw,
    Trash2,
    Plus,
    Pencil,
    Cpu,
    MessageSquareText,
    Check,
    SlidersHorizontal,
} from "lucide-react";
import { Separator } from "@/components/ui/separator";
import {
    fetchConfig,
    createArticleType,
    deleteArticleType,
    updateRule,
    createCheckSection,
    type Config,
    type ArticleType,
    type CheckSection,
    type Rule,
    type ParamSchema,
} from "@/lib/api";

type DraftRules = Record<string, Record<string, Rule>>;

function buildDraft(articleTypes: ArticleType[]): DraftRules {
    const draft: DraftRules = {};
    for (const t of articleTypes) {
        draft[t.id] = { ...(t.rules || {}) };
    }
    return draft;
}

function isDraftDirty(draft: DraftRules, articleTypes: ArticleType[]): boolean {
    for (const t of articleTypes) {
        const original = t.rules || {};
        const current = draft[t.id] || {};
        const keys = new Set([
            ...Object.keys(original),
            ...Object.keys(current),
        ]);
        for (const key of keys) {
            if (
                JSON.stringify(original[key]) !== JSON.stringify(current[key])
            ) {
                return true;
            }
        }
    }
    return false;
}

interface ConfigMatrixProps {
    activeJournalId: string;
    activeArticleTypeId: string;
    setActiveArticleTypeId: (id: string) => void;
}

export function ConfigMatrix({
    activeJournalId,
    activeArticleTypeId,
    setActiveArticleTypeId,
}: ConfigMatrixProps) {
    const [config, setConfig] = useState<Config | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [draftRules, setDraftRules] = useState<DraftRules>({});
    const [newTypeName, setNewTypeName] = useState("");
    const [editingCell, setEditingCell] = useState<{
        typeId: string;
        sectionKey: string;
    } | null>(null);
    const [editInstruction, setEditInstruction] = useState("");
    const [selectedContextFields, setSelectedContextFields] = useState<
        string[]
    >([]);
    const [editingParams, setEditingParams] = useState<{
        typeId: string;
        sectionKey: string;
        schema: ParamSchema[];
        draft: Record<string, string>; // param key -> raw string value
    } | null>(null);

    // Article type delete modal state
    const [isDeleteArticleTypeOpen, setIsDeleteArticleTypeOpen] =
        useState(false);
    const [isDeletingArticleType, setIsDeletingArticleType] = useState(false);

    // New check section modal state
    const [isAddCheckOpen, setIsAddCheckOpen] = useState(false);
    const [newCheckName, setNewCheckName] = useState("");
    const [newCheckDesc, setNewCheckDesc] = useState("");
    const [newCheckInstruction, setNewCheckInstruction] = useState("");
    const [newCheckContextFields, setNewCheckContextFields] = useState<
        string[]
    >([]);
    const [creatingCheck, setCreatingCheck] = useState(false);

    // Available metadata fields for custom LLM context
    const METADATA_FIELDS = [
        { value: "abstract", label: "Abstract" },
        { value: "titleName", label: "Title" },
        { value: "authorInformation", label: "Author Information" },
        { value: "keywords", label: "Keywords" },
        { value: "conflictOfInterest", label: "Conflict of Interest" },
        { value: "htcta", label: "How to Cite This Article" },
        { value: "date_format", label: "Date Fields" },
        { value: "online_access", label: "Online Access Block" },
    ];

    const activeJournal = config?.journals.find(
        (j) => j.id === activeJournalId,
    );
    const activeArticleType = activeJournal?.article_types?.find(
        (t) => t.id === activeArticleTypeId,
    );

    const reload = useCallback(async () => {
        setLoading(true);
        try {
            const c = await fetchConfig();
            setConfig(c);

            // Rebuild draft for the currently active journal
            const journal = c.journals.find((j) => j.id === activeJournalId);
            if (journal) {
                setDraftRules(buildDraft(journal.article_types || []));
            }
        } catch (err) {
            console.error("Failed to load config:", err);
        } finally {
            setLoading(false);
        }
    }, [activeJournalId]);

    useEffect(() => {
        reload();
    }, [reload]);

    // Whenever activeJournalId changes, update the draft rules
    useEffect(() => {
        if (activeJournal) {
            setDraftRules(buildDraft(activeJournal.article_types || []));
        }
    }, [activeJournal]);

    // ── Local draft mutations ──────────────────────

    const patchDraft = (
        typeId: string,
        sectionKey: string,
        patch: Partial<Rule>,
    ) => {
        setDraftRules((prev) => {
            const typeDraft = { ...(prev[typeId] || {}) };
            typeDraft[sectionKey] = {
                ...(typeDraft[sectionKey] || { type: "general" }),
                ...patch,
            };
            return { ...prev, [typeId]: typeDraft };
        });
    };

    const handleToggleEnabled = (
        typeId: string,
        sectionKey: string,
        enabled: boolean,
    ) => {
        patchDraft(typeId, sectionKey, { enabled });
    };

    const handleToggleType = (articleType: ArticleType, sectionKey: string) => {
        const currentRule = draftRules[articleType.id]?.[sectionKey] || {
            type: "general",
        };
        if (currentRule.type === "general") {
            setEditInstruction("");
            setEditingCell({ typeId: articleType.id, sectionKey });
        } else {
            patchDraft(articleType.id, sectionKey, {
                type: "general",
                instruction: undefined,
            });
        }
    };

    const handleSaveCustomInstruction = () => {
        if (!editingCell) return;
        patchDraft(editingCell.typeId, editingCell.sectionKey, {
            type: "custom",
            instruction: editInstruction,
            params: { context_fields: selectedContextFields },
        });
        setEditingCell(null);
    };

    // ── Effective params helper ───────────────────────────────────
    // Reads the params from the current draft for a given rule, with
    // fallback to the config's default_rules params.
    const getEffectiveParams = (
        sectionKey: string,
        typeId: string,
    ): Record<string, unknown> => {
        const draftRule = draftRules[typeId]?.[sectionKey];
        if (draftRule?.params)
            return draftRule.params as Record<string, unknown>;
        // Fall back to default_rules in config
        const defaultRules = (
            config as Config & {
                default_rules?: Record<
                    string,
                    { params?: Record<string, unknown> }
                >;
            }
        )?.default_rules;
        return defaultRules?.[sectionKey]?.params ?? {};
    };

    const handleOpenParams = (typeId: string, section: CheckSection) => {
        if (!section.params_schema) return;
        const current = getEffectiveParams(section.key, typeId);
        const draft: Record<string, string> = {};
        for (const s of section.params_schema) {
            const val = current[s.key];
            if (s.type === "string_list" && Array.isArray(val)) {
                draft[s.key] = (val as string[]).join("\n");
            } else {
                draft[s.key] = (val as string) ?? "";
            }
        }
        setEditingParams({
            typeId,
            sectionKey: section.key,
            schema: section.params_schema,
            draft,
        });
    };

    const handleSaveParams = () => {
        if (!editingParams) return;
        const { typeId, sectionKey, schema, draft } = editingParams;
        const params: Record<string, unknown> = {};
        for (const s of schema) {
            if (s.type === "string_list") {
                params[s.key] = draft[s.key]
                    .split("\n")
                    .map((l) => l.trim())
                    .filter(Boolean);
            } else {
                params[s.key] = draft[s.key].trim();
            }
        }
        patchDraft(typeId, sectionKey, { params });
        setEditingParams(null);
    };

    const handleSave = async () => {
        if (!activeJournal || !activeArticleType) return;
        setSaving(true);
        try {
            const original = activeArticleType.rules || {};
            const current = draftRules[activeArticleTypeId] || {};
            const keys = new Set([
                ...Object.keys(original),
                ...Object.keys(current),
            ]);

            // Sequential saves: each request must fully commit before the next
            // one reads config.json, otherwise concurrent reads of the same
            // stale snapshot cause later writes to silently drop earlier ones.
            for (const key of keys) {
                if (
                    JSON.stringify(original[key]) !==
                    JSON.stringify(current[key])
                ) {
                    await updateRule(
                        activeJournalId,
                        activeArticleTypeId,
                        key,
                        current[key],
                    );
                }
            }

            toast.success("已儲存變更");
            await reload();
        } catch (err) {
            console.error("Failed to save changes:", err);
            toast.error("儲存失敗，請重試");
        } finally {
            setSaving(false);
        }
    };

    const handleReset = () => {
        if (activeJournal)
            setDraftRules(buildDraft(activeJournal.article_types || []));
    };

    // ── Article Type CRUD ─────────────────────────────────────────────

    const handleAddArticleType = async () => {
        if (!newTypeName.trim()) return;
        try {
            await createArticleType(activeJournalId, newTypeName);
            setNewTypeName("");
            toast.success(`成功新增文章類型: ${newTypeName}`);
            await reload();
        } catch (err) {
            console.error("Failed to add article type:", err);
            toast.error("新增文章類型失敗");
        }
    };

    const handleDeleteArticleType = async () => {
        if (!activeArticleType) return;
        setIsDeletingArticleType(true);
        try {
            await deleteArticleType(activeJournalId, activeArticleType.id);
            toast.success("已刪除文章類型");
            await reload();
            setIsDeleteArticleTypeOpen(false);
        } catch (err) {
            console.error("Failed to delete article type:", err);
            toast.error("刪除文章類型失敗");
        } finally {
            setIsDeletingArticleType(false);
        }
    };

    // ── Check Section CRUD ─────────────────────────────────────────────

    const resetAddCheckModal = () => {
        setIsAddCheckOpen(false);
        setNewCheckName("");
        setNewCheckDesc("");
        setNewCheckInstruction("");
        setNewCheckContextFields([]);
    };

    const handleCreateCheckSection = async () => {
        if (!newCheckName.trim() || !newCheckInstruction.trim()) return;
        setCreatingCheck(true);
        try {
            await createCheckSection({
                name: newCheckName.trim(),
                description: newCheckDesc.trim() || undefined,
                instruction: newCheckInstruction.trim(),
                context_fields: newCheckContextFields,
                target_journal_id: activeJournalId,
                target_article_type_id: activeArticleTypeId,
            });
            toast.success("成功新增檢查項目");
            await reload();
            resetAddCheckModal();
        } catch (err) {
            console.error("Failed to create check section:", err);
            toast.error("新增檢查項目失敗");
        } finally {
            setCreatingCheck(false);
        }
    };

    // ── Render ───────────────────────────────────────────────────

    if (loading || !config) {
        return (
            <div className="flex items-center justify-center py-20 text-muted-foreground text-sm">
                載入設定中...
            </div>
        );
    }

    if (!activeArticleType) return null;

    const { check_sections } = config;
    // Only check if the active article type is dirty
    const dirty = isDraftDirty(draftRules, [activeArticleType]);

    const subheadingsParams = getEffectiveParams(
        "subheadings",
        activeArticleTypeId,
    );
    const expectedHeadings = subheadingsParams.expected_headings as
        | string[]
        | undefined;
    const bodyHeadingsArray = expectedHeadings || [
        "Introduction",
        "Materials and Methods",
        "Results",
        "Discussion",
        "Conclusions",
    ];

    const dynamicSectionFields = bodyHeadingsArray.filter(Boolean).map((h) => ({
        value: `section:${h.trim()}`,
        label: `§ ${h.trim()}`,
    }));

    return (
        <div className="space-y-6">
            {/* Top bar: Add Article Type + Save/Reset */}
            <div className="flex items-center justify-between gap-4">
                <div className="flex items-center justify-between w-full">
                    <div className="flex items-center gap-6">
                        {/* Add Article type dropdown here */}
                        <div className="flex items-center gap-3">
                            <span className="text-sm font-medium">
                                文章類型:
                            </span>
                            <Select
                                value={activeArticleTypeId}
                                onValueChange={setActiveArticleTypeId}
                                disabled={
                                    loading ||
                                    !activeJournal ||
                                    activeJournal.article_types.length === 0
                                }
                            >
                                <SelectTrigger className="w-[200px]">
                                    <SelectValue placeholder="選擇文章類型" />
                                </SelectTrigger>
                                <SelectContent>
                                    {activeJournal?.article_types.map((t) => (
                                        <SelectItem key={t.id} value={t.id}>
                                            {t.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="w-px h-6 bg-border/60" />
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="flex gap-4">
                            <Input
                                placeholder="新增此期刊的文章類型 (例如: Case Report)..."
                                value={newTypeName}
                                onChange={(e) => setNewTypeName(e.target.value)}
                                onKeyDown={(e) =>
                                    e.key === "Enter" && handleAddArticleType()
                                }
                                className="w-[300px]"
                            />
                            <Button
                                onClick={handleAddArticleType}
                                disabled={!newTypeName.trim()}
                                className="gap-2 shrink-0"
                            >
                                <Plus className="w-4 h-4" />
                                新增文章類型
                            </Button>
                        </div>
                        <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => setIsDeleteArticleTypeOpen(true)}
                            className="gap-2"
                            disabled={isDeletingArticleType}
                        >
                            <Trash2 className="w-4 h-4" />
                            {isDeletingArticleType
                                ? "刪除中..."
                                : "刪除文章類型"}
                        </Button>
                    </div>
                </div>

                {dirty && (
                    <div className="flex items-center gap-2 animate-in fade-in slide-in-from-right-4 duration-200">
                        <span className="text-xs text-muted-foreground">
                            有未儲存的變更
                        </span>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleReset}
                            disabled={saving}
                            className="gap-1.5"
                        >
                            <RotateCcw className="w-3.5 h-3.5" />
                            還原
                        </Button>
                        <Button
                            size="sm"
                            onClick={handleSave}
                            disabled={saving}
                            className="gap-1.5"
                        >
                            <Save className="w-3.5 h-3.5" />
                            {saving ? "儲存中..." : "儲存變更"}
                        </Button>
                    </div>
                )}
            </div>

            {/* Matrix Table */}
            <div className="rounded-xl border border-border/50 overflow-hidden bg-card text-card-foreground shadow-sm">
                <Table>
                    <TableHeader>
                        <TableRow className="bg-muted/30 border-b border-border/50">
                            <TableHead className="w-[20%] font-semibold text-foreground py-4 px-6">
                                檢查項目
                            </TableHead>
                            <TableHead className="w-[35%] font-semibold text-foreground py-4 px-6">
                                通則說明
                            </TableHead>
                            <TableHead className="w-[45%] text-left font-semibold text-foreground py-4 px-6 relative">
                                <div className="flex items-center justify-between">
                                    <span>{activeArticleType.name}</span>
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        className="gap-1.5 h-8 text-xs absolute right-6 top-1/2 -translate-y-1/2"
                                        onClick={() => setIsAddCheckOpen(true)}
                                    >
                                        <Plus className="w-3.5 h-3.5" />
                                        新增檢查項目
                                    </Button>
                                </div>
                            </TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {check_sections.map((section: CheckSection) => {
                            const rule = draftRules[activeArticleTypeId]?.[
                                section.key
                            ] || {
                                type: "general",
                            };
                            const isCustom = rule.type === "custom";
                            const isEnabled = rule.enabled !== false;

                            return (
                                <TableRow
                                    key={section.key}
                                    className="hover:bg-muted/10 transition-colors border-b border-border/40 group"
                                >
                                    <TableCell className="font-semibold text-sm text-foreground align-top p-6">
                                        {section.display_name}
                                    </TableCell>
                                    <TableCell className="text-[13px] text-muted-foreground whitespace-pre-line leading-relaxed align-top p-6 pr-10">
                                        {section.general_description || "—"}
                                    </TableCell>

                                    {/* Active Article Type Cell Content */}
                                    <TableCell
                                        className={`transition-all align-top p-6 ${!isEnabled ? "opacity-40 bg-muted/5 grayscale" : ""}`}
                                    >
                                        <div className="flex items-start justify-between gap-8">
                                            {/* Column 1: Custom/General Badge & Edit Button */}
                                            <div className="flex flex-col gap-3.5 min-w-[200px] flex-grow">
                                                <div className="flex items-center gap-3 flex-wrap">
                                                    <Badge
                                                        variant={
                                                            isCustom
                                                                ? "secondary"
                                                                : "default"
                                                        }
                                                        className={`whitespace-nowrap px-3 py-1 text-xs font-medium cursor-pointer transition-all shadow-sm ${
                                                            isEnabled
                                                                ? "hover:ring-2 hover:ring-primary/20 hover:-translate-y-px"
                                                                : "cursor-not-allowed"
                                                        }`}
                                                        onClick={() => {
                                                            if (isEnabled)
                                                                handleToggleType(
                                                                    activeArticleType,
                                                                    section.key,
                                                                );
                                                        }}
                                                    >
                                                        {isCustom ? (
                                                            <span className="flex items-center gap-1.5">
                                                                <Cpu className="w-3.5 h-3.5" />
                                                                自訂 LLM 指令
                                                            </span>
                                                        ) : (
                                                            <span>
                                                                遵循預設通則
                                                            </span>
                                                        )}
                                                    </Badge>

                                                    {isCustom && isEnabled && (
                                                        <Button
                                                            variant="outline"
                                                            size="sm"
                                                            className="h-7 px-2.5 text-xs shadow-sm gap-1.5 transition-all text-muted-foreground hover:text-foreground hover:border-primary/30"
                                                            onClick={() => {
                                                                if (isEnabled) {
                                                                    setEditInstruction(
                                                                        rule.instruction ||
                                                                            "",
                                                                    );
                                                                    const cf = (
                                                                        rule.params as
                                                                            | {
                                                                                  context_fields?: string[];
                                                                              }
                                                                            | undefined
                                                                    )
                                                                        ?.context_fields;
                                                                    setSelectedContextFields(
                                                                        cf ??
                                                                            [],
                                                                    );
                                                                    setEditingCell(
                                                                        {
                                                                            typeId: activeArticleTypeId,
                                                                            sectionKey:
                                                                                section.key,
                                                                        },
                                                                    );
                                                                }
                                                            }}
                                                        >
                                                            <Pencil className="w-3 h-3" />
                                                            編輯自訂指令
                                                        </Button>
                                                    )}

                                                    {/* Edit Params button — for checks with a params_schema */}
                                                    {section.params_schema &&
                                                        section.params_schema
                                                            .length > 0 &&
                                                        isEnabled && (
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                className="h-7 px-2.5 text-xs shadow-sm gap-1.5 transition-all text-muted-foreground hover:text-foreground hover:border-primary/30"
                                                                onClick={() =>
                                                                    handleOpenParams(
                                                                        activeArticleTypeId,
                                                                        section,
                                                                    )
                                                                }
                                                            >
                                                                <SlidersHorizontal className="w-3 h-3" />
                                                                編輯參數
                                                            </Button>
                                                        )}
                                                </div>

                                                <div className="min-h-[2.5rem]">
                                                    {isCustom &&
                                                        rule.instruction &&
                                                        isEnabled && (
                                                            <div className="text-[13px] text-foreground/90 bg-muted/40 px-3.5 py-3 rounded-lg border border-border/60 shadow-inner flex gap-3">
                                                                <MessageSquareText className="w-4 h-4 mt-0.5 shrink-0 text-primary/80" />
                                                                <span className="leading-relaxed whitespace-pre-wrap">
                                                                    {
                                                                        rule.instruction
                                                                    }
                                                                </span>
                                                            </div>
                                                        )}
                                                    {isCustom &&
                                                        !rule.instruction &&
                                                        isEnabled && (
                                                            <div className="text-[13px] text-amber-600/90 bg-amber-50/50 dark:bg-amber-950/20 px-3.5 py-2.5 rounded-lg border border-amber-200/50 dark:border-amber-900/50 flex items-start gap-2.5">
                                                                ⚠️{" "}
                                                                <span className="pt-0.5">
                                                                    請點擊上方按鈕輸入自訂條件
                                                                </span>
                                                            </div>
                                                        )}
                                                </div>
                                            </div>

                                            {/* Column 2: Enable/Disable Switch */}
                                            <div className="flex flex-col items-center justify-start gap-2.5 shrink-0 pl-8 border-l border-border/40">
                                                <div
                                                    className={`flex flex-col items-center gap-1.5 bg-background px-3 py-3 rounded-xl border shadow-sm transition-colors ${isEnabled ? "border-primary/20 shadow-primary/5" : "border-border/50"}`}
                                                >
                                                    <Switch
                                                        checked={isEnabled}
                                                        onCheckedChange={(
                                                            checked: boolean,
                                                        ) =>
                                                            handleToggleEnabled(
                                                                activeArticleType.id,
                                                                section.key,
                                                                checked,
                                                            )
                                                        }
                                                        className="data-[state=checked]:bg-primary"
                                                    />
                                                    <span
                                                        className={`text-[11px] font-bold tracking-wider ${isEnabled ? "text-primary" : "text-muted-foreground"}`}
                                                    >
                                                        {isEnabled
                                                            ? "ON"
                                                            : "OFF"}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </div>
            {/* Custom Instruction Dialog */}
            <Dialog
                open={!!editingCell}
                onOpenChange={(open) => {
                    if (!open) setEditingCell(null);
                }}
            >
                <DialogContent className="sm:max-w-lg">
                    <DialogHeader>
                        <DialogTitle>自訂 LLM 指令</DialogTitle>
                        <DialogDescription>
                            輸入自訂檢查指令，系統會使用 LLM
                            依據此指令檢查文件。
                        </DialogDescription>
                    </DialogHeader>
                    <textarea
                        value={editInstruction}
                        onChange={(e) => setEditInstruction(e.target.value)}
                        placeholder="例如：檢查摘要是否包含研究目的、方法、結果和結論四個部分..."
                        className="w-full min-h-[120px] rounded-lg border border-input bg-background px-3 py-2 text-sm resize-y focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                    {/* Context fields selector */}
                    <div className="space-y-2">
                        <p className="text-sm font-medium">LLM 可讀取的欄位</p>
                        <p className="text-xs text-muted-foreground">
                            選擇 LLM 在執行上方指令時可參考哪些資料。{" "}
                            <span className="font-bold">僅可存取文字資訊</span>
                        </p>
                        <div className="grid grid-cols-2 gap-1.5">
                            {[...METADATA_FIELDS, ...dynamicSectionFields].map(
                                (f) => {
                                    const isSection =
                                        f.value.startsWith("section:");
                                    const checked =
                                        selectedContextFields.includes(f.value);
                                    return (
                                        <label
                                            key={f.value}
                                            className={`flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-xs cursor-pointer transition-colors ${
                                                checked
                                                    ? "border-primary bg-primary/5 text-foreground"
                                                    : "border-border text-muted-foreground hover:border-primary/40"
                                            }`}
                                        >
                                            <input
                                                type="checkbox"
                                                className="accent-primary"
                                                checked={checked}
                                                onChange={() =>
                                                    setSelectedContextFields(
                                                        (prev) =>
                                                            checked
                                                                ? prev.filter(
                                                                      (v) =>
                                                                          v !==
                                                                          f.value,
                                                                  )
                                                                : [
                                                                      ...prev,
                                                                      f.value,
                                                                  ],
                                                    )
                                                }
                                            />
                                            <span>{f.label}</span>
                                            {isSection && (
                                                <span
                                                    className="ml-auto text-[10px] text-amber-500"
                                                    title="PDF section text may be imprecise for complex layouts"
                                                >
                                                    ⚠
                                                </span>
                                            )}
                                        </label>
                                    );
                                },
                            )}
                        </div>
                    </div>
                    <DialogFooter>
                        <DialogClose asChild>
                            <Button variant="outline">取消</Button>
                        </DialogClose>
                        <Button
                            onClick={handleSaveCustomInstruction}
                            className="gap-2"
                        >
                            <Check className="w-4 h-4" />
                            套用
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Params Edit Dialog */}
            <Dialog
                open={!!editingParams}
                onOpenChange={(open) => {
                    if (!open) setEditingParams(null);
                }}
            >
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <SlidersHorizontal className="w-4 h-4" />
                            編輯參數
                        </DialogTitle>
                        <DialogDescription>
                            調整此檢查項目的參數設定。儲存後需點擊「儲存變更」才會生效。
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4">
                        {editingParams?.schema.map((s) => (
                            <div key={s.key} className="space-y-1.5">
                                <label className="text-sm font-medium">
                                    {s.label}
                                </label>
                                {s.hint && (
                                    <p className="text-xs text-muted-foreground">
                                        {s.hint}
                                    </p>
                                )}
                                {s.type === "string_list" ? (
                                    <textarea
                                        value={editingParams.draft[s.key] ?? ""}
                                        onChange={(e) =>
                                            setEditingParams((prev) =>
                                                prev
                                                    ? {
                                                          ...prev,
                                                          draft: {
                                                              ...prev.draft,
                                                              [s.key]:
                                                                  e.target
                                                                      .value,
                                                          },
                                                      }
                                                    : null,
                                            )
                                        }
                                        rows={6}
                                        className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm font-mono resize-y focus:outline-none focus:ring-2 focus:ring-ring"
                                        placeholder={`e.g.\nBackground:\nObjectives:\nResults:`}
                                    />
                                ) : (
                                    <Input
                                        value={editingParams.draft[s.key] ?? ""}
                                        onChange={(e) =>
                                            setEditingParams((prev) =>
                                                prev
                                                    ? {
                                                          ...prev,
                                                          draft: {
                                                              ...prev.draft,
                                                              [s.key]:
                                                                  e.target
                                                                      .value,
                                                          },
                                                      }
                                                    : null,
                                            )
                                        }
                                        placeholder={s.hint}
                                        className="font-mono text-sm"
                                    />
                                )}
                            </div>
                        ))}
                    </div>

                    <DialogFooter>
                        <DialogClose asChild>
                            <Button variant="outline">取消</Button>
                        </DialogClose>
                        <Button onClick={handleSaveParams} className="gap-2">
                            <Check className="w-4 h-4" />
                            套用
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Add Check Section Dialog */}
            <Dialog
                open={isAddCheckOpen}
                onOpenChange={(open) => {
                    if (!open) resetAddCheckModal();
                }}
            >
                <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>新增檢查項目</DialogTitle>
                        <DialogDescription>
                            為此文件類型新增一個全新的自訂檢查項目。
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">
                                檢查項目名稱{" "}
                                <span className="text-destructive">*</span>
                            </label>
                            <Input
                                placeholder="例如：自訂圖片格式檢查"
                                value={newCheckName}
                                onChange={(e) =>
                                    setNewCheckName(e.target.value)
                                }
                                disabled={creatingCheck}
                            />
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">
                                通則說明
                            </label>
                            <Input
                                placeholder="簡單描述這個檢查項目的用途..."
                                value={newCheckDesc}
                                onChange={(e) =>
                                    setNewCheckDesc(e.target.value)
                                }
                                disabled={creatingCheck}
                            />
                        </div>

                        <Separator className="my-2" />

                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">
                                自訂 LLM 指令{" "}
                                <span className="text-destructive">*</span>
                            </label>
                            <p className="text-xs text-muted-foreground">
                                輸入 LLM 在檢查此項目時所需要遵循的指令。
                            </p>
                            <textarea
                                value={newCheckInstruction}
                                onChange={(e) =>
                                    setNewCheckInstruction(e.target.value)
                                }
                                placeholder="例如：請檢查圖片解析度是否符合..."
                                className="w-full min-h-[100px] rounded-lg border border-input bg-background px-3 py-2 text-sm resize-y focus:outline-none focus:ring-2 focus:ring-ring"
                                disabled={creatingCheck}
                            />
                        </div>

                        <div className="space-y-2">
                            <p className="text-sm font-medium">
                                LLM 可讀取的欄位
                            </p>
                            <div className="grid grid-cols-2 gap-1.5">
                                {[
                                    ...METADATA_FIELDS,
                                    ...dynamicSectionFields,
                                ].map((f) => {
                                    const isSection =
                                        f.value.startsWith("section:");
                                    const checked =
                                        newCheckContextFields.includes(f.value);
                                    return (
                                        <label
                                            key={`new-check-${f.value}`}
                                            className={`flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-xs cursor-pointer transition-colors ${
                                                checked
                                                    ? "border-primary bg-primary/5 text-foreground"
                                                    : "border-border text-muted-foreground hover:border-primary/40"
                                            } ${creatingCheck ? "opacity-50 cursor-not-allowed" : ""}`}
                                        >
                                            <input
                                                type="checkbox"
                                                className="accent-primary"
                                                checked={checked}
                                                disabled={creatingCheck}
                                                onChange={() => {
                                                    if (creatingCheck) return;
                                                    setNewCheckContextFields(
                                                        (prev) =>
                                                            checked
                                                                ? prev.filter(
                                                                      (v) =>
                                                                          v !==
                                                                          f.value,
                                                                  )
                                                                : [
                                                                      ...prev,
                                                                      f.value,
                                                                  ],
                                                    );
                                                }}
                                            />
                                            <span>{f.label}</span>
                                            {isSection && (
                                                <span className="ml-auto text-[10px] text-amber-500">
                                                    ⚠
                                                </span>
                                            )}
                                        </label>
                                    );
                                })}
                            </div>
                        </div>
                    </div>

                    <DialogFooter>
                        <DialogClose asChild>
                            <Button variant="outline" disabled={creatingCheck}>
                                取消
                            </Button>
                        </DialogClose>
                        <Button
                            onClick={handleCreateCheckSection}
                            disabled={
                                !newCheckName.trim() ||
                                !newCheckInstruction.trim() ||
                                creatingCheck
                            }
                            className="gap-2"
                        >
                            {creatingCheck ? (
                                "新增中..."
                            ) : (
                                <>
                                    <Check className="w-4 h-4" />
                                    新增
                                </>
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Delete Article Type Alert Dialog */}
            <AlertDialog
                open={isDeleteArticleTypeOpen}
                onOpenChange={setIsDeleteArticleTypeOpen}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>
                            確定要刪除此文章類型嗎？
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                            這將會永久刪除「{activeArticleType.name}
                            」以及它底下的所有規則設定，此操作無法復原。
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={isDeletingArticleType}>
                            取消
                        </AlertDialogCancel>
                        <Button
                            variant="destructive"
                            onClick={handleDeleteArticleType}
                            disabled={isDeletingArticleType}
                        >
                            {isDeletingArticleType ? "刪除中..." : "確認刪除"}
                        </Button>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
