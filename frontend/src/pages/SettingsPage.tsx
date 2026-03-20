import { useState, useEffect } from "react";
import { ConfigMatrix } from "@/components/ConfigMatrix";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
    DialogClose,
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
import {
    Settings,
    ArrowLeft,
    Plus,
    Trash2,
    Eye,
    EyeOff,
    Save,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
    fetchJournals,
    createJournal,
    deleteJournal,
    type Journal,
    fetchGlobalSettings,
    updateGlobalSettings,
} from "@/lib/api";

export default function SettingsPage() {
    const [journals, setJournals] = useState<Journal[]>([]);
    const [activeJournalId, setActiveJournalId] = useState<string>("");
    const [activeArticleTypeId, setActiveArticleTypeId] = useState<string>("");
    const [loading, setLoading] = useState(true);
    const [newJournalName, setNewJournalName] = useState("");
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
    const [creating, setCreating] = useState(false);
    const [deleting, setDeleting] = useState(false);

    // Global Settings
    const [apiKey, setApiKey] = useState("");
    const [isApiKeyVisible, setIsApiKeyVisible] = useState(false);
    const [savingApiKey, setSavingApiKey] = useState(false);

    const activeJournal = journals.find((j) => j.id === activeJournalId);

    useEffect(() => {
        const loadJournals = async () => {
            try {
                const data = await fetchJournals();
                setJournals(data);
                if (data.length > 0) {
                    const firstJournal = data[0];
                    setActiveJournalId(firstJournal.id);
                    if (
                        firstJournal.article_types &&
                        firstJournal.article_types.length > 0
                    ) {
                        setActiveArticleTypeId(
                            firstJournal.article_types[0].id,
                        );
                    }
                }
            } catch (err) {
                console.error("Failed to load journals:", err);
                toast.error("讀取期刊失敗");
            } finally {
                setLoading(false);
            }
        };

        const loadGlobalSettings = async () => {
            try {
                const settings = await fetchGlobalSettings();
                if (settings && settings.api_key) {
                    setApiKey(settings.api_key);
                }
            } catch (err) {
                console.error("Failed to load global settings:", err);
            }
        };

        loadJournals();
        loadGlobalSettings();
    }, []);

    const handleCreateJournal = async () => {
        const trimmed = newJournalName.trim();
        if (!trimmed) return;
        setCreating(true);
        try {
            const created = await createJournal(trimmed);
            setJournals((prev) => [...prev, created]);
            setActiveJournalId(created.id);
            if (created.article_types?.length > 0) {
                setActiveArticleTypeId(created.article_types[0].id);
            }
            setNewJournalName("");
            setIsCreateOpen(false);
            toast.success(`成功新增期刊: ${created.name}`);
        } catch (err) {
            console.error("Failed to create journal:", err);
            toast.error("新增期刊失敗，請重試");
        } finally {
            setCreating(false);
        }
    };

    const handleDeleteJournal = async () => {
        if (!activeJournalId) return;
        setDeleting(true);
        try {
            await deleteJournal(activeJournalId);
            const remaining = journals.filter((j) => j.id !== activeJournalId);
            setJournals(remaining);
            if (remaining.length > 0) {
                setActiveJournalId(remaining[0].id);
                setActiveArticleTypeId(
                    remaining[0].article_types?.[0]?.id ?? "",
                );
            } else {
                setActiveJournalId("");
                setActiveArticleTypeId("");
            }
            toast.success("已成功刪除期刊");
        } catch (err) {
            console.error("Failed to delete journal:", err);
            toast.error("刪除期刊失敗，請重試");
        } finally {
            setDeleting(false);
            setIsDeleteDialogOpen(false);
        }
    };

    // When activeJournalId changes, update the activeArticleTypeId
    useEffect(() => {
        if (
            activeJournal &&
            activeJournal.article_types &&
            activeJournal.article_types.length > 0
        ) {
            // Check if current type is valid for new journal, if not, pick the first one
            if (
                !activeJournal.article_types.find(
                    (t) => t.id === activeArticleTypeId,
                )
            ) {
                setActiveArticleTypeId(activeJournal.article_types[0].id);
            }
        } else {
            setActiveArticleTypeId("");
        }
    }, [activeJournalId, journals]);

    {
        /* Main Content */
    }
    const handleSaveApiKey = async () => {
        setSavingApiKey(true);
        try {
            await updateGlobalSettings({ api_key: apiKey.trim() });
            toast.success("系統設定已儲存");
        } catch (err) {
            console.error("Failed to save API key:", err);
            toast.error("儲存失敗，請重試");
        } finally {
            setSavingApiKey(false);
        }
    };

    return (
        <div className="min-h-screen bg-background">
            {/* Header */}
            <header className="border-b border-border/40 bg-card/50 backdrop-blur-sm sticky top-0 z-50">
                <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
                            <Settings className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                            <h1 className="text-lg font-semibold tracking-tight">
                                Configuration
                            </h1>
                        </div>
                    </div>
                    <Link to="/">
                        <Button variant="ghost" size="sm" className="gap-2">
                            <ArrowLeft className="w-4 h-4" />
                            返回校對頁面
                        </Button>
                    </Link>
                </div>
            </header>

            {/* Main Content */}
            <main className="max-w-6xl mx-auto px-6 py-8">
                <div className="space-y-8">
                    {/* Global Settings Section */}
                    <div className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden p-6 space-y-4">
                        <div>
                            <h2 className="text-xl font-bold tracking-tight">
                                系統設定
                            </h2>
                            <p className="text-sm text-muted-foreground mt-1">
                                設定環境變數與 AI 的 API 資訊
                            </p>
                        </div>
                        <div className="grid gap-2 max-w-xl">
                            <label className="text-sm font-medium">
                                Gemini API Key
                            </label>
                            <div className="flex gap-2">
                                <div className="relative flex-1">
                                    <Input
                                        type={
                                            isApiKeyVisible
                                                ? "text"
                                                : "password"
                                        }
                                        placeholder="輸入 Google Gemini API Key"
                                        value={apiKey}
                                        onChange={(e) =>
                                            setApiKey(e.target.value)
                                        }
                                        className="pr-10 font-mono text-sm"
                                    />
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        className="absolute right-0 top-0 h-full w-10 text-muted-foreground hover:text-foreground"
                                        onClick={() =>
                                            setIsApiKeyVisible(!isApiKeyVisible)
                                        }
                                    >
                                        {isApiKeyVisible ? (
                                            <EyeOff className="h-4 w-4" />
                                        ) : (
                                            <Eye className="h-4 w-4" />
                                        )}
                                    </Button>
                                </div>
                                <Button
                                    onClick={handleSaveApiKey}
                                    disabled={savingApiKey}
                                    className="gap-2 min-w-[100px]"
                                >
                                    <Save className="h-4 w-4" />
                                    {savingApiKey ? "儲存中" : "儲存設定"}
                                </Button>
                            </div>
                        </div>
                    </div>

                    <Separator className="bg-border/40" />

                    <div className="flex items-center justify-between ">
                        <div>
                            <h2 className="text-xl font-bold tracking-tight">
                                檢查規則設定欄
                            </h2>
                            <p className="text-sm text-muted-foreground mt-1">
                                為不同的期刊與文章類型設定不同的檢查規則與指令
                            </p>
                        </div>

                        {/* Journal Selector + CRUD */}
                        <div className="flex items-center gap-3">
                            {/* Journal dropdown */}
                            <div className="flex items-center gap-3">
                                <span className="text-sm font-medium">
                                    目前的期刊:
                                </span>
                                <Select
                                    value={activeJournalId}
                                    onValueChange={setActiveJournalId}
                                    disabled={loading || journals.length === 0}
                                >
                                    <SelectTrigger className="w-[200px]">
                                        <SelectValue placeholder="選擇期刊" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {journals.map((j) => (
                                            <SelectItem key={j.id} value={j.id}>
                                                {j.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            {/* Delete journal button triggers dialog */}
                            <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => setIsDeleteDialogOpen(true)}
                                disabled={loading || !activeJournal}
                                className="gap-2"
                            >
                                <Trash2 className="w-4 h-4" />
                                刪除期刊
                            </Button>

                            {/* Create new journal — opens modal */}
                            <Button
                                size="sm"
                                onClick={() => setIsCreateOpen(true)}
                            >
                                <Plus className="w-3.5 h-3.5" />
                                新增期刊
                            </Button>
                        </div>
                    </div>
                    <Separator />

                    {/* Only render ConfigMatrix if we have a selected journal */}
                    {!loading && activeJournalId && activeArticleTypeId ? (
                        <ConfigMatrix
                            activeJournalId={activeJournalId}
                            activeArticleTypeId={activeArticleTypeId}
                            setActiveArticleTypeId={setActiveArticleTypeId}
                        />
                    ) : !loading && journals.length === 0 ? (
                        <div className="text-center py-16 text-muted-foreground">
                            <p className="text-sm">
                                尚未新增任何期刊，請先在左側新增期刊
                            </p>
                        </div>
                    ) : null}
                </div>
            </main>

            {/* Create Journal Modal */}
            <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                <DialogContent className="sm:max-w-[425px]">
                    <DialogHeader>
                        <DialogTitle>新增期刊</DialogTitle>
                        <DialogDescription>
                            請輸入新期刊的名稱，建立後可為其設定不同的文章類型與檢查規則。
                        </DialogDescription>
                    </DialogHeader>
                    <div className="py-4">
                        <Input
                            placeholder="期刊名稱 (例如: Nature)..."
                            value={newJournalName}
                            onChange={(e) => setNewJournalName(e.target.value)}
                            onKeyDown={(e) =>
                                e.key === "Enter" && handleCreateJournal()
                            }
                            autoFocus
                            disabled={creating}
                        />
                    </div>
                    <DialogFooter>
                        <DialogClose asChild>
                            <Button variant="outline" disabled={creating}>
                                取消
                            </Button>
                        </DialogClose>
                        <Button
                            onClick={handleCreateJournal}
                            disabled={!newJournalName.trim() || creating}
                            className="gap-1.5"
                        >
                            {creating ? "新增中..." : "建立期刊"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Delete Journal Alert Dialog */}
            <AlertDialog
                open={isDeleteDialogOpen}
                onOpenChange={setIsDeleteDialogOpen}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>確定要刪除期刊嗎？</AlertDialogTitle>
                        <AlertDialogDescription>
                            這將會永久刪除「{activeJournal?.name ?? "此期刊"}
                            」以及其底下的所有文章類型與檢查設定，此操作無法復原。
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={deleting}>
                            取消
                        </AlertDialogCancel>
                        <Button
                            variant="destructive"
                            onClick={handleDeleteJournal}
                            disabled={deleting}
                        >
                            {deleting ? "刪除中..." : "確認刪除"}
                        </Button>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
