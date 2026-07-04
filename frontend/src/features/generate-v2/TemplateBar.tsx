import { useEffect, useState } from 'react';
import { Save, Trash2, Loader2, FileText } from 'lucide-react';
import { Button, Card, CardContent } from '@/components/ui';
import {
  PipelineTemplate,
  PipelineTemplatePayload,
  createTemplate,
  deleteTemplate,
  listTemplates,
} from '@/lib/api/pipelineTemplates';
import { useLanguage } from '@/contexts/LanguageContext';

interface TemplateBarProps {
  onApply: (payload: unknown) => void;
  onDump: () => PipelineTemplatePayload;
}

export default function TemplateBar({ onApply, onDump }: TemplateBarProps) {
  const { t } = useLanguage();
  const [templates, setTemplates] = useState<PipelineTemplate[]>([]);
  const [selected, setSelected] = useState<number | ''>('');
  const [loading, setLoading] = useState(false);
  const [showSave, setShowSave] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await listTemplates();
      setTemplates(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load templates');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const handleApply = () => {
    const tpl = templates.find((t) => t.id === selected);
    if (!tpl) return;
    onApply(tpl.payload);
  };

  const handleSave = async () => {
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const payload = onDump();
      await createTemplate({ name: name.trim(), description: description.trim() || undefined, payload });
      setShowSave(false);
      setName('');
      setDescription('');
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save template');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!selected) return;
    if (!confirm(t('generateV2.templateConfirmDelete') || 'Delete this template?')) return;
    setLoading(true);
    setError(null);
    try {
      await deleteTemplate(Number(selected));
      setSelected('');
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete template');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardContent className="p-3 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <FileText className="w-4 h-4 text-[var(--muted)]" />
          <span className="text-sm text-[var(--muted)] mr-1">
            {t('generateV2.templates') || 'Templates'}:
          </span>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value ? Number(e.target.value) : '')}
            disabled={loading || templates.length === 0}
            className="text-sm bg-black/30 border border-white/10 rounded px-2 py-1 text-white focus:outline-none focus:border-teal-500 min-w-[200px]"
          >
            <option value="">
              {templates.length === 0
                ? t('generateV2.noTemplates') || 'No templates yet'
                : t('generateV2.selectTemplate') || 'Select template…'}
            </option>
            {templates.map((tpl) => (
              <option key={tpl.id} value={tpl.id} className="bg-gray-800">
                {tpl.name}
              </option>
            ))}
          </select>
          <Button size="sm" variant="secondary" onClick={handleApply} disabled={!selected || loading}>
            {t('generateV2.applyTemplate') || 'Apply'}
          </Button>
          <Button size="sm" variant="ghost" onClick={handleDelete} disabled={!selected || loading}>
            <Trash2 className="w-3 h-3" />
          </Button>
          <div className="flex-1" />
          <Button size="sm" onClick={() => setShowSave((v) => !v)} disabled={loading}>
            <Save className="w-3 h-3" />
            {t('generateV2.saveAsTemplate') || 'Save as template'}
          </Button>
        </div>

        {showSave && (
          <div className="border-t border-white/10 pt-2 space-y-2">
            <input
              type="text"
              placeholder={t('generateV2.templateName') || 'Template name'}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full text-sm bg-black/30 border border-white/10 rounded px-2 py-1.5 text-white focus:outline-none focus:border-teal-500"
            />
            <input
              type="text"
              placeholder={t('generateV2.templateDescription') || 'Description (optional)'}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full text-sm bg-black/30 border border-white/10 rounded px-2 py-1.5 text-white focus:outline-none focus:border-teal-500"
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={handleSave} disabled={!name.trim() || loading}>
                {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                {t('generateV2.save') || 'Save'}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setShowSave(false)} disabled={loading}>
                {t('generateV2.cancel') || 'Cancel'}
              </Button>
            </div>
          </div>
        )}

        {error && <div className="text-xs text-red-400">{error}</div>}
      </CardContent>
    </Card>
  );
}
