import React, { useMemo, useState } from 'react';
import type { WellProfile } from '../../api/asset';

/**
 * v0.6 ED-8 (F-28 rev., D-37): completion diagram drawn natively from the well's structured
 * construction data (TC-029 profile) — no server image. Casing + cement, tubing and downhole
 * tools, perforations by status, formation tops, PBTD / TD, hover details, non-overlapping
 * call-outs, and a perforation table. "Completion zone" zooms to the producing interval.
 */

type Profile = Pick<WellProfile, 'identity' | 'construction' | 'lithology'>;

const W = 640;
const H = 720;
const TOP = 34;
const BOTTOM = 26;
const AXIS_X = 46;
const FORM_X = 56;
const FORM_W = 92;
const CX = 268; // wellbore centre line
const CALLOUT_X = 392;
const LABEL_GAP = 24;

const FORMATION_COLORS = ['#3b3a2e', '#2f3b33', '#3a3226', '#2c3640', '#3d2f36', '#33302a', '#283a3a'];
const C_CASING = '#cbd5e1';
const C_CEMENT = '#6b7280';
const C_TUBING = '#60a5fa';
const C_OPEN = '#ef4444';
const C_SQZ = '#9ca3af';
const C_TOOL = '#38bdf8';
const C_TEXT = '#e6edf3';
const C_MUTED = '#8b949e';

const casingHalfWidth = (od: number) => 14 + od * 2.3;
const TUBING_HW = 8;

interface Callout {
  key: string;
  depth: number;
  title: string;
  sub: string;
  color: string;
  anchorX: number;
}

interface HoverInfo {
  title: string;
  lines: string[];
}

const fmt = (v: number | null | undefined, d = 1) => (v == null || Number.isNaN(v) ? '—' : v.toFixed(d));
const isOpen = (s: string | null) => (s ?? '').toUpperCase() === 'OPEN';
const pretty = (s: string) => s.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());

/** Spread label y-positions so they never overlap (keeps order, stays inside the plot). */
function layoutLabels(ys: number[], minY: number, maxY: number, gap: number): number[] {
  const out = [...ys];
  for (let i = 1; i < out.length; i++) out[i] = Math.max(out[i], out[i - 1] + gap);
  const overflow = out.length ? out[out.length - 1] - maxY : 0;
  if (overflow > 0) {
    out[out.length - 1] -= overflow;
    for (let i = out.length - 2; i >= 0; i--) out[i] = Math.min(out[i], out[i + 1] - gap);
  }
  return out.map((y) => Math.max(minY, y));
}

export const CompletionDiagram: React.FC<{ profile: Profile }> = ({ profile }) => {
  const [zoom, setZoom] = useState<'full' | 'completion'>('full');
  const [hover, setHover] = useState<HoverInfo | null>(null);

  const { identity, construction, lithology } = profile;
  const casing = useMemo(
    () => [...(construction.casing || [])].filter((c) => c.shoe_m != null).sort((a, b) => (b.od_in ?? 0) - (a.od_in ?? 0)),
    [construction.casing],
  );
  const tubing = useMemo(() => [...(construction.tubing || [])].sort((a, b) => a.seq - b.seq), [construction.tubing]);
  const perfs = useMemo(() => [...(construction.perfs || [])].sort((a, b) => a.top_m - b.top_m), [construction.perfs]);

  const shoes = casing.map((c) => c.shoe_m as number);
  const td = identity.total_depth_md_m ?? Math.max(1000, ...shoes, ...perfs.map((p) => p.bottom_m));
  const prodCasing = casing.find((c) => c.string_type.toUpperCase().includes('PROD')) ?? casing[casing.length - 1];
  const pbtd = prodCasing?.shoe_m ?? (shoes.length ? Math.max(...shoes) : td);
  const eot = tubing.reduce((m, t) => Math.max(m, (t.top_m ?? 0) + (t.length_m ?? 0)), 0);
  const tools = tubing.filter((t) => t.component.toUpperCase() !== 'TUBING');

  // Completion zone = from the shallowest perforation / packer / pump / anchor (minus a margin) to TD.
  const zone = useMemo(() => {
    const keyDepths = [
      ...perfs.map((p) => p.top_m),
      ...tools.filter((t) => ['PACKER', 'PUMP', 'TUBING_ANCHOR'].includes(t.component.toUpperCase())).map((t) => t.top_m ?? td),
    ];
    const start = keyDepths.length ? Math.min(...keyDepths) : td * 0.8;
    const span = td - start;
    return { start: Math.max(0, start - Math.max(60, span * 0.5)), end: td + Math.max(10, span * 0.08) };
  }, [perfs, tools, td]);

  // Full well uses a scale break so the completion zone keeps 45% of the height ("not to scale" below the break).
  const plotH = H - TOP - BOTTOM;
  const BREAK_FRAC = 0.55;
  const d0 = zoom === 'full' ? 0 : zone.start;
  const d1 = zoom === 'full' ? Math.max(td + 10, zone.end) : zone.end;
  const hasBreak = zoom === 'full' && zone.start > 0.35 * d1;
  const y = (d: number) => {
    if (!hasBreak) return TOP + ((d - d0) / (d1 - d0)) * plotH;
    if (d <= zone.start) return TOP + (d / zone.start) * plotH * BREAK_FRAC;
    return TOP + plotH * BREAK_FRAC + ((d - zone.start) / (d1 - zone.start)) * plotH * (1 - BREAK_FRAC);
  };
  const yc = (d: number) => Math.min(Math.max(y(d), TOP), TOP + plotH);
  const inView = (a: number, b = a) => b >= d0 && a <= d1;

  // Depth ticks (per segment when the scale is broken)
  const ticks = useMemo(() => {
    const segTicks = (a: number, b: number, n: number) => {
      const raw = (b - a) / n;
      const mag = 10 ** Math.floor(Math.log10(raw));
      const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((st) => st >= raw) ?? raw;
      const out: number[] = [];
      for (let d = Math.ceil(a / step) * step; d <= b + 1e-6; d += step) out.push(d);
      return out;
    };
    if (!hasBreak) return segTicks(d0, d1, 7);
    return [...segTicks(0, zone.start, 4).filter((d) => d < zone.start - (zone.start * 0.06)), ...segTicks(zone.start, d1, 4)];
  }, [d0, d1, hasBreak, zone.start]);

  const innerHW = prodCasing ? casingHalfWidth(prodCasing.od_in) : 26;

  // Call-outs (right side), laid out without overlap
  const callouts = useMemo(() => {
    const items: Callout[] = [];
    casing.forEach((c) => {
      if (inView(c.shoe_m as number))
        items.push({
          key: `cs-${c.string_type}`,
          depth: c.shoe_m as number,
          title: `${pretty(c.string_type)} ${c.od_in}" ${c.grade ?? ''}`.trim(),
          sub: `Shoe ${fmt(c.shoe_m)} m · TOC ${fmt(c.cement_top_m)} m`,
          color: C_CASING,
          anchorX: CX + casingHalfWidth(c.od_in),
        });
    });
    const glms = tools.filter((t) => t.component.toUpperCase() === 'GLM' && inView(t.top_m ?? 0));
    if (glms.length)
      items.push({
        key: 'glm',
        depth: glms[glms.length - 1].top_m ?? 0,
        title: `${glms.length} gas-lift mandrel${glms.length > 1 ? 's' : ''}`,
        sub: glms.map((g) => `${fmt(g.top_m, 0)}`).join(' / ') + ' m',
        color: C_TOOL,
        anchorX: CX + TUBING_HW + 6,
      });
    tools
      .filter((t) => t.component.toUpperCase() !== 'GLM' && inView(t.top_m ?? 0))
      .forEach((t) =>
        items.push({
          key: `tool-${t.seq}`,
          depth: t.top_m ?? 0,
          title: pretty(t.component),
          sub: `Set @ ${fmt(t.top_m)} m${t.od_in ? ` · ${t.od_in}"` : ''}`,
          color: C_TOOL,
          anchorX: CX + (t.component.toUpperCase() === 'PACKER' ? innerHW : TUBING_HW + 4),
        }),
      );
    perfs.forEach((p, i) => {
      if (inView(p.top_m, p.bottom_m))
        items.push({
          key: `perf-${i}`,
          depth: (p.top_m + p.bottom_m) / 2,
          title: `${p.zone} perfs · ${(p.status ?? '—').toUpperCase()}`,
          sub: `${fmt(p.top_m)}–${fmt(p.bottom_m)} m${p.spf ? ` · ${p.spf} SPF` : ''}`,
          color: isOpen(p.status) ? C_OPEN : C_SQZ,
          anchorX: CX + innerHW + 22,
        });
    });
    if (inView(pbtd)) items.push({ key: 'pbtd', depth: pbtd, title: 'PBTD', sub: `${fmt(pbtd)} m MD`, color: C_TEXT, anchorX: CX + innerHW });
    if (inView(td)) items.push({ key: 'td', depth: td, title: 'TD', sub: `${fmt(td)} m MD`, color: C_TEXT, anchorX: CX + innerHW + 10 });
    items.sort((a, b) => a.depth - b.depth);
    const ys = layoutLabels(items.map((c) => y(c.depth)), TOP + 6, TOP + plotH - 4, LABEL_GAP);
    return items.map((c, i) => ({ ...c, labelY: ys[i] }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [casing, tools, perfs, pbtd, td, d0, d1, innerHW, hasBreak, zone.start]);

  const hoverProps = (info: HoverInfo) => ({
    onMouseEnter: () => setHover(info),
    onMouseLeave: () => setHover(null),
    style: { cursor: 'help' } as React.CSSProperties,
  });

  const noData = !casing.length && !perfs.length && !tubing.length;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-1 text-[11px] font-sans">
        {(
          [
            ['full', 'Full well'],
            ['completion', 'Completion zone'],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            type="button"
            onClick={() => setZoom(k)}
            className={`px-2 py-0.5 rounded border ${zoom === k ? 'border-accent text-white bg-accent/20' : 'border-border text-textMuted hover:text-white'}`}
          >
            {label}
          </button>
        ))}
        <span className="ml-auto text-[10px] font-mono text-textMuted min-h-[14px] truncate" aria-live="polite">
          {hover ? (
            <>
              <span className="text-white font-semibold">{hover.title}</span> · {hover.lines.join(' · ')}
            </>
          ) : (
            'Hover any element for details · depths m MD'
          )}
        </span>
      </div>

      {noData ? (
        <div className="text-xs text-textMuted p-6 border border-dashed border-border rounded text-center">
          Construction data not recorded for this well.
        </div>
      ) : (
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full h-auto rounded bg-[#0b0f14] border border-border/60"
          role="img"
          aria-label={`Completion diagram for ${identity.well_id}`}
          data-testid="completion-diagram"
        >
          <defs>
            <pattern id="cement-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="6" height="6" fill={C_CEMENT} opacity="0.35" />
              <line x1="0" y1="0" x2="0" y2="6" stroke={C_CEMENT} strokeWidth="2" opacity="0.8" />
            </pattern>
            <clipPath id="plot-clip">
              <rect x="0" y={TOP} width={W} height={plotH} />
            </clipPath>
          </defs>

          <text x={AXIS_X} y={18} fill={C_MUTED} fontSize="10" fontFamily="ui-monospace,monospace">
            m MD
          </text>
          <text x={FORM_X + FORM_W / 2} y={18} fill={C_MUTED} fontSize="10" textAnchor="middle">
            Formation
          </text>
          <text x={CX} y={18} fill={C_MUTED} fontSize="10" textAnchor="middle">
            {identity.well_id} · TD {fmt(td, 0)} m
          </text>

          {/* depth axis + grid */}
          <line x1={AXIS_X} y1={TOP} x2={AXIS_X} y2={TOP + plotH} stroke="#30363d" />
          {hasBreak && (
            <g>
              <line x1={AXIS_X - 30} y1={y(zone.start)} x2={FORM_X + FORM_W} y2={y(zone.start)} stroke="#f59e0b" strokeOpacity="0.7" strokeDasharray="6 4" />
              <path d={`M ${AXIS_X - 5} ${y(zone.start) - 5} l 5 3 l -5 3 l 5 3`} fill="none" stroke="#f59e0b" strokeWidth="1.2" />
            </g>
          )}
          {ticks.map((d) => (
            <g key={d}>
              <line x1={AXIS_X - 4} y1={y(d)} x2={W - 8} y2={y(d)} stroke="#1f2630" strokeDasharray="2 4" />
              <text x={AXIS_X - 6} y={y(d) + 3} fill={C_MUTED} fontSize="9" textAnchor="end" fontFamily="ui-monospace,monospace">
                {Math.round(d)}
              </text>
            </g>
          ))}

          <g clipPath="url(#plot-clip)">
            {/* formations */}
            {lithology.map((l, i) => {
              if (!inView(l.top_md_m, l.bottom_md_m)) return null;
              const yt = yc(l.top_md_m);
              const yb = yc(l.bottom_md_m);
              return (
                <g
                  key={l.formation}
                  {...hoverProps({
                    title: l.formation,
                    lines: [`${fmt(l.top_md_m, 0)}–${fmt(l.bottom_md_m, 0)} m`, l.lithology],
                  })}
                >
                  <rect x={FORM_X} y={yt} width={FORM_W} height={Math.max(yb - yt, 1)} fill={FORMATION_COLORS[i % FORMATION_COLORS.length]} stroke="#0b0f14" />
                  {yb - yt > 14 && (
                    <text x={FORM_X + 5} y={yt + 12} fill={C_TEXT} fontSize="10" fontWeight="600">
                      {l.formation}
                    </text>
                  )}
                  {yb - yt > 28 && (
                    <text x={FORM_X + 5} y={yt + 24} fill={C_MUTED} fontSize="8.5" fontFamily="ui-monospace,monospace">
                      top {fmt(l.top_md_m, 0)} m
                    </text>
                  )}
                  {/* faint band across the wellbore area for the reservoir */}
                  <rect x={FORM_X + FORM_W} y={yt} width={CALLOUT_X - FORM_X - FORM_W - 12} height={Math.max(yb - yt, 1)} fill={FORMATION_COLORS[i % FORMATION_COLORS.length]} opacity="0.25" />
                </g>
              );
            })}

            {/* cement (outside each casing, from TOC to shoe) */}
            {casing.map((c) => {
              if (c.cement_top_m == null) return null;
              const hw = casingHalfWidth(c.od_in);
              const yt = yc(c.cement_top_m);
              const yb = yc(c.shoe_m as number);
              if (yb - yt <= 0) return null;
              return (
                <g key={`cem-${c.string_type}`} {...hoverProps({ title: `Cement · ${pretty(c.string_type)}`, lines: [`TOC ${fmt(c.cement_top_m)} m → shoe ${fmt(c.shoe_m)} m`] })}>
                  <rect x={CX - hw - 8} y={yt} width={8} height={yb - yt} fill="url(#cement-hatch)" />
                  <rect x={CX + hw} y={yt} width={8} height={yb - yt} fill="url(#cement-hatch)" />
                </g>
              );
            })}

            {/* casing strings */}
            {casing.map((c) => {
              const hw = casingHalfWidth(c.od_in);
              const yt = yc(c.top_m ?? 0);
              const yb = yc(c.shoe_m as number);
              const showShoe = inView(c.shoe_m as number);
              return (
                <g
                  key={`cs-${c.string_type}`}
                  {...hoverProps({
                    title: `${pretty(c.string_type)} casing`,
                    lines: [`${c.od_in}" ${c.grade ?? ''}${c.weight_ppf ? ` ${c.weight_ppf} ppf` : ''}`.trim(), `${fmt(c.top_m ?? 0, 0)}–${fmt(c.shoe_m)} m`, `TOC ${fmt(c.cement_top_m)} m`],
                  })}
                >
                  <line x1={CX - hw} y1={yt} x2={CX - hw} y2={yb} stroke={C_CASING} strokeWidth="3" />
                  <line x1={CX + hw} y1={yt} x2={CX + hw} y2={yb} stroke={C_CASING} strokeWidth="3" />
                  {showShoe && (
                    <>
                      <polygon points={`${CX - hw},${yb} ${CX - hw - 7},${yb} ${CX - hw},${yb - 8}`} fill={C_CASING} />
                      <polygon points={`${CX + hw},${yb} ${CX + hw + 7},${yb} ${CX + hw},${yb - 8}`} fill={C_CASING} />
                    </>
                  )}
                </g>
              );
            })}

            {/* perforations */}
            {perfs.map((p, i) => {
              if (!inView(p.top_m, p.bottom_m)) return null;
              const yt = yc(p.top_m);
              const yb = yc(p.bottom_m);
              const h = Math.max(yb - yt, 3);
              const open = isOpen(p.status);
              const n = Math.max(2, Math.min(14, Math.floor(h / 4)));
              const color = open ? C_OPEN : C_SQZ;
              return (
                <g
                  key={`perf-${i}`}
                  {...hoverProps({
                    title: `${p.zone} perforations · ${(p.status ?? '—').toUpperCase()}`,
                    lines: [`${fmt(p.top_m)}–${fmt(p.bottom_m)} m (${fmt(p.bottom_m - p.top_m)} m)`, `${p.spf ?? '—'} SPF`, `shot ${p.perf_date ?? '—'}`],
                  })}
                >
                  <rect x={CX + innerHW} y={yt} width={22} height={h} fill={color} opacity={open ? 0.18 : 0.1} />
                  <rect x={CX - innerHW - 22} y={yt} width={22} height={h} fill={color} opacity={open ? 0.18 : 0.1} />
                  {Array.from({ length: n }).map((_, k) => {
                    const yy = yt + ((k + 0.5) * h) / n;
                    return (
                      <g key={k}>
                        <line x1={CX + innerHW} y1={yy} x2={CX + innerHW + 20} y2={yy} stroke={color} strokeWidth="1.6" strokeDasharray={open ? undefined : '2 2'} />
                        <line x1={CX - innerHW - 20} y1={yy} x2={CX - innerHW} y2={yy} stroke={color} strokeWidth="1.6" strokeDasharray={open ? undefined : '2 2'} />
                      </g>
                    );
                  })}
                </g>
              );
            })}

            {/* tubing */}
            {eot > 0 && (
              <g {...hoverProps({ title: 'Tubing string', lines: [`${construction.tubing_size_in ?? tubing[0]?.od_in ?? '—'}"`, `surface → EOT ${fmt(eot)} m`] })}>
                <line x1={CX - TUBING_HW} y1={yc(0)} x2={CX - TUBING_HW} y2={yc(eot)} stroke={C_TUBING} strokeWidth="2.2" />
                <line x1={CX + TUBING_HW} y1={yc(0)} x2={CX + TUBING_HW} y2={yc(eot)} stroke={C_TUBING} strokeWidth="2.2" />
              </g>
            )}

            {/* downhole tools */}
            {tools.map((t) => {
              const comp = t.component.toUpperCase();
              const yt = y(t.top_m ?? 0);
              const yb = y((t.top_m ?? 0) + Math.max(t.length_m ?? 1, 1));
              const h = Math.max(yb - yt, 6);
              const info = { title: pretty(t.component), lines: [`@ ${fmt(t.top_m)} m`, t.length_m ? `${fmt(t.length_m)} m long` : '', t.od_in ? `${t.od_in}"` : ''].filter(Boolean) };
              if (!inView(t.top_m ?? 0)) return null;
              if (comp === 'PACKER')
                return (
                  <g key={t.seq} {...hoverProps(info)}>
                    <rect x={CX - innerHW + 1} y={yt - 3} width={innerHW - TUBING_HW - 1} height={Math.max(h, 9)} fill="#111827" stroke={C_TOOL} strokeWidth="1.2" />
                    <rect x={CX + TUBING_HW} y={yt - 3} width={innerHW - TUBING_HW - 1} height={Math.max(h, 9)} fill="#111827" stroke={C_TOOL} strokeWidth="1.2" />
                    <line x1={CX - innerHW + 1} y1={yt - 3} x2={CX - TUBING_HW} y2={yt + Math.max(h, 9) - 3} stroke={C_TOOL} />
                    <line x1={CX + TUBING_HW} y1={yt + Math.max(h, 9) - 3} x2={CX + innerHW - 1} y2={yt - 3} stroke={C_TOOL} />
                  </g>
                );
              if (comp === 'PUMP')
                return (
                  <g key={t.seq} {...hoverProps(info)}>
                    <rect x={CX - TUBING_HW - 2} y={yt} width={(TUBING_HW + 2) * 2} height={Math.max(h, 12)} rx="2" fill={C_TOOL} opacity="0.85" />
                    <text x={CX} y={yt + Math.max(h, 12) / 2 + 3} fill="#0b0f14" fontSize="7.5" fontWeight="700" textAnchor="middle">
                      P
                    </text>
                  </g>
                );
              if (comp === 'TUBING_ANCHOR')
                return (
                  <g key={t.seq} {...hoverProps(info)}>
                    {[-1, 1].map((s) => (
                      <polyline
                        key={s}
                        points={`${CX + s * TUBING_HW},${yt} ${CX + s * (TUBING_HW + 7)},${yt + 3} ${CX + s * TUBING_HW},${yt + 6}`}
                        fill="none"
                        stroke={C_TOOL}
                        strokeWidth="1.6"
                      />
                    ))}
                  </g>
                );
              if (comp === 'GLM')
                return (
                  <g key={t.seq} {...hoverProps(info)}>
                    <rect x={CX + TUBING_HW} y={yt - 4} width={6} height={9} fill={C_TOOL} />
                  </g>
                );
              return (
                <g key={t.seq} {...hoverProps(info)}>
                  <rect x={CX - TUBING_HW - 1} y={yt} width={(TUBING_HW + 1) * 2} height={6} fill={C_TOOL} />
                </g>
              );
            })}

            {/* PBTD / TD */}
            {inView(pbtd) && (
              <g {...hoverProps({ title: 'PBTD', lines: [`${fmt(pbtd)} m MD`] })}>
                <line x1={CX - innerHW} y1={y(pbtd)} x2={CX + innerHW} y2={y(pbtd)} stroke={C_TEXT} strokeWidth="2" strokeDasharray="5 3" />
              </g>
            )}
            {inView(td) && (
              <g {...hoverProps({ title: 'Total depth', lines: [`${fmt(td)} m MD`] })}>
                <line x1={CX - innerHW - 30} y1={y(td)} x2={CX + innerHW + 30} y2={y(td)} stroke={C_TEXT} strokeWidth="1.2" />
              </g>
            )}
          </g>

          {/* call-outs */}
          {callouts.map((c) => (
            <g key={c.key}>
              <polyline
                points={`${c.anchorX + 2},${y(c.depth)} ${CALLOUT_X - 14},${y(c.depth)} ${CALLOUT_X - 4},${c.labelY}`}
                fill="none"
                stroke={c.color}
                strokeOpacity="0.55"
                strokeWidth="0.8"
              />
              <text x={CALLOUT_X} y={c.labelY - 1} fill={c.color} fontSize="10" fontWeight="600">
                {c.title}
              </text>
              <text x={CALLOUT_X} y={c.labelY + 10} fill={C_MUTED} fontSize="9" fontFamily="ui-monospace,monospace">
                {c.sub}
              </text>
            </g>
          ))}
        </svg>
      )}

      {/* legend */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] font-mono text-textMuted">
        <span className="flex items-center gap-1"><span className="w-4 border-t-2" style={{ borderColor: C_CASING }} />Casing</span>
        <span className="flex items-center gap-1"><span className="w-3 h-2.5" style={{ background: C_CEMENT, opacity: 0.7 }} />Cement</span>
        <span className="flex items-center gap-1"><span className="w-4 border-t-2" style={{ borderColor: C_TUBING }} />Tubing</span>
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: C_TOOL }} />Downhole tool</span>
        <span className="flex items-center gap-1"><span className="w-4 border-t-2" style={{ borderColor: C_OPEN }} />Open perfs</span>
        <span className="flex items-center gap-1"><span className="w-4 border-t-2 border-dashed" style={{ borderColor: C_SQZ }} />Squeezed perfs</span>
        <span className="flex items-center gap-1"><span className="w-4 border-t-2 border-dashed" style={{ borderColor: C_TEXT }} />PBTD</span>
        {hasBreak && (
          <span className="flex items-center gap-1 text-amber-300/90">
            <span className="w-4 border-t-2 border-dashed border-amber-400/80" />
            Scale break at {Math.round(zone.start)} m: completion zone expanded below
          </span>
        )}
      </div>

      {/* perforation table */}
      <div className="overflow-x-auto">
        <table className="w-full text-[11px] font-mono" data-testid="perforation-table">
          <thead className="text-textMuted">
            <tr className="border-b border-border">
              <th className="text-left py-1 pr-2">Zone</th>
              <th className="text-right pr-2">Top m</th>
              <th className="text-right pr-2">Bottom m</th>
              <th className="text-right pr-2">Length m</th>
              <th className="text-right pr-2">SPF</th>
              <th className="text-left pr-2">Shot</th>
              <th className="text-left">Status</th>
            </tr>
          </thead>
          <tbody>
            {perfs.length ? (
              perfs.map((p, i) => (
                <tr key={i} className="border-b border-border/40 text-textMain">
                  <td className="py-1 pr-2 text-white">{p.zone}</td>
                  <td className="text-right pr-2">{fmt(p.top_m)}</td>
                  <td className="text-right pr-2">{fmt(p.bottom_m)}</td>
                  <td className="text-right pr-2">{fmt(p.bottom_m - p.top_m)}</td>
                  <td className="text-right pr-2">{p.spf ?? '—'}</td>
                  <td className="pr-2">{p.perf_date ?? '—'}</td>
                  <td>
                    <span
                      className={`px-1.5 rounded border text-[10px] ${
                        isOpen(p.status) ? 'border-red-700/60 text-red-300 bg-red-950/40' : 'border-slate-600 text-slate-300 bg-slate-800/50'
                      }`}
                    >
                      {(p.status ?? '—').toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7} className="py-2 text-textMuted">
                  Perforation intervals not recorded.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
