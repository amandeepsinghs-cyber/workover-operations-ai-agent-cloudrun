import React from 'react';
import { UserCog } from 'lucide-react';
import { usePersona, Persona, PERSONAS } from '../../state/persona';
import { t, Lang } from '../../i18n/strings';

export const PersonaPicker: React.FC<{ lang?: Lang; compact?: boolean }> = ({
  lang = 'english',
  compact = false,
}) => {
  const { persona, setPersona, capabilities } = usePersona();

  return (
    <div
      className="h-7 inline-flex items-center gap-1.5 px-2 bg-[#0d1117] border border-border rounded-lg text-xs font-mono text-white"
      title={t('persona.demo_note', lang)}
    >
      <UserCog className="w-3.5 h-3.5 text-textMuted shrink-0" />
      {!compact && (
        <span className="text-[9px] font-mono uppercase bg-blue-900/60 text-blue-300 border border-blue-700/50 px-1.5 py-0.5 rounded font-semibold shrink-0">
          DEMO
        </span>
      )}
      <select
        data-testid="persona-picker"
        aria-label={t('persona.label', lang)}
        value={persona}
        onChange={(e) => setPersona(e.target.value as Persona)}
        className="bg-transparent text-white font-mono text-xs focus:outline-none cursor-pointer"
      >
        {PERSONAS.map((p) => (
          <option key={p} value={p} className="bg-[#0d1117] text-white">
            {t(`persona.${p}`, lang)}
          </option>
        ))}
      </select>
      {Boolean(capabilities && capabilities.denied && capabilities.denied.length > 0) && (
        <span
          className="text-[10px] text-textMuted font-mono shrink-0 pl-1 border-l border-border"
          title={capabilities!.denied.join(', ')}
        >
          {capabilities!.denied.length} views restricted
        </span>
      )}
    </div>
  );
};

export default PersonaPicker;
