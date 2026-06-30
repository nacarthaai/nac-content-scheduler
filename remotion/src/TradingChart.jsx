const { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, spring } = require("remotion");
const { HUDPanel, ConfidenceMeter, SignalBadge, ScoreChip, ScanLine, DigitalGrid, PnLCallout } = require("./HUD");
const { BrandBar } = require("./KineticText");

// ── Frame phase constants (35s = 1050 frames @ 30fps) ──────────────────────
const F = {
  HUD_IN:       0,    // HUD panels boot
  HUD_DONE:     60,
  CHART_START:  90,   // candles begin drawing
  CHART_END:    600,  // all candles visible
  RSI_START:    420,  // RSI panel draws in
  SIGNAL_IN:    570,  // signal badge appears
  CONF_IN:      570,  // confidence meter starts
  ENTRY_IN:     660,  // entry arrow flash
  EXIT_IN:      870,  // exit arrow + P&L
  PNL_IN:       900,
  WIN_IN:       960,
};

// ── Candlestick SVG ─────────────────────────────────────────────────────────
const Candles = ({ candles, visibleCount, priceToY, xStep, candleW, entryIdx, exitIdx, entryFrame, exitFrame }) => {
  const frame = useCurrentFrame();
  return (
    <g>
      {candles.slice(0, visibleCount).map((c, i) => {
        const x = i * xStep + xStep * 0.5;
        const oY = priceToY(c.o);
        const cY = priceToY(c.c);
        const hY = priceToY(c.h);
        const lY = priceToY(c.l);
        const isGreen = c.c >= c.o;
        const color = isGreen ? "#22c55e" : "#ef4444";
        const bodyY = Math.min(oY, cY);
        const bodyH = Math.max(Math.abs(cY - oY), 2);

        // Fade-in for newest candle
        const isNewest = i === visibleCount - 1;
        const candleOpacity = isNewest ? interpolate(
          frame,
          [F.CHART_START + i * (F.CHART_END - F.CHART_START) / candles.length,
           F.CHART_START + (i + 1) * (F.CHART_END - F.CHART_START) / candles.length],
          [0.3, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        ) : 1;

        // Entry/exit glow
        const isEntry = i === entryIdx && frame >= F.ENTRY_IN;
        const isExit  = i === exitIdx  && frame >= F.EXIT_IN;

        return (
          <g key={i} opacity={candleOpacity}>
            {/* Wick */}
            <line x1={x} y1={hY} x2={x} y2={lY} stroke={color} strokeWidth={1.5} opacity={0.7}/>
            {/* Body */}
            <rect x={x - candleW / 2} y={bodyY} width={candleW} height={bodyH}
              fill={isGreen ? `${color}cc` : color}
              stroke={color} strokeWidth={0.5}
              filter={isEntry || isExit ? "url(#glow)" : undefined}
            />
            {/* Entry marker */}
            {isEntry && (
              <g>
                <line x1={x} y1={hY - 24} x2={x} y2={hY - 8} stroke="#f59e0b" strokeWidth={2} strokeDasharray="4,2"/>
                <polygon points={`${x},${hY - 6} ${x-8},${hY - 20} ${x+8},${hY - 20}`} fill="#f59e0b"/>
                <text x={x} y={hY - 30} textAnchor="middle" fill="#f59e0b" fontSize={14} fontWeight="bold">ENTRY</text>
              </g>
            )}
            {/* Exit marker */}
            {isExit && (
              <g>
                <line x1={x} y1={lY + 8} x2={x} y2={lY + 24} stroke="#a78bfa" strokeWidth={2} strokeDasharray="4,2"/>
                <polygon points={`${x},${lY + 6} ${x-8},${lY + 20} ${x+8},${lY + 20}`} fill="#a78bfa" transform={`rotate(180,${x},${lY + 13})`}/>
                <text x={x} y={lY + 38} textAnchor="middle" fill="#a78bfa" fontSize={14} fontWeight="bold">EXIT</text>
              </g>
            )}
          </g>
        );
      })}
    </g>
  );
};

// ── RSI line chart ───────────────────────────────────────────────────────────
const RSILine = ({ rsi, visibleCount, rsiW, rsiH }) => {
  const frame = useCurrentFrame();
  const rsiProgress = interpolate(frame, [F.RSI_START, F.RSI_START + 120], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const validRsi = rsi.filter(v => v != null);
  if (!validRsi.length) return null;

  const rsiVisible = Math.max(1, Math.floor(rsiProgress * Math.min(visibleCount, validRsi.length)));
  const xStep = rsiW / validRsi.length;

  const points = validRsi.slice(0, rsiVisible).map((v, i) => {
    const x = i * xStep + xStep * 0.5;
    const y = rsiH - (v / 100) * rsiH;
    return `${x},${y}`;
  }).join(" ");

  const lastRsi = validRsi[rsiVisible - 1];
  const rsiColor = lastRsi > 70 ? "#ef4444" : lastRsi < 30 ? "#22c55e" : "#f59e0b";

  return (
    <g>
      {/* Overbought/oversold zones */}
      <rect x={0} y={0} width={rsiW} height={rsiH * 0.3} fill="#ef444408"/>
      <rect x={0} y={rsiH * 0.7} width={rsiW} height={rsiH * 0.3} fill="#22c55e08"/>
      <line x1={0} y1={rsiH * 0.3} x2={rsiW} y2={rsiH * 0.3} stroke="#ef444433" strokeWidth={1} strokeDasharray="4,4"/>
      <line x1={0} y1={rsiH * 0.7} x2={rsiW} y2={rsiH * 0.7} stroke="#22c55e33" strokeWidth={1} strokeDasharray="4,4"/>
      {/* RSI line */}
      {points && <polyline points={points} fill="none" stroke={rsiColor} strokeWidth={2} opacity={0.9}/>}
      {/* Current RSI label */}
      {rsiVisible > 0 && (
        <text x={rsiW - 4} y={12} textAnchor="end" fill={rsiColor} fontSize={14} fontWeight="bold">
          RSI {Math.round(lastRsi)}
        </text>
      )}
    </g>
  );
};

// ── Volume bars ──────────────────────────────────────────────────────────────
const VolumeBars = ({ candles, visibleCount, volW, volH }) => {
  const maxVol = Math.max(...candles.map(c => c.v));
  return (
    <g>
      {candles.slice(0, visibleCount).map((c, i) => {
        const xStep = volW / candles.length;
        const x = i * xStep;
        const barH = (c.v / maxVol) * volH * 0.9;
        const color = c.c >= c.o ? "#22c55e" : "#ef4444";
        return (
          <rect key={i} x={x + 1} y={volH - barH} width={xStep - 2} height={barH}
            fill={color} opacity={0.4}/>
        );
      })}
    </g>
  );
};

// ── Main TradingChart composition ────────────────────────────────────────────
const TradingChart = ({
  ticker = "TSLA",
  candles = [],
  rsi = [],
  direction = "SHORT",
  pnl = -50,
  score = 65,
  strategy = "intraday",
  entryIdx = 20,
  exitIdx = 28,
  support = 0,
  resistance = 0,
  hudColor = "#00e5ff",  // theme-driven HUD accent color
  bgGradientStart = "#080810",
  bgGradientEnd = "#000000",
  grain = 0.25,
  vignette = 0.4,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  // ── Layout constants ───────────────────────────────────────────────────────
  const PAD = 30;
  const CHART_TOP    = 280;
  const CHART_BOTTOM = 1120;
  const CHART_H      = CHART_BOTTOM - CHART_TOP;
  const CHART_W      = width - PAD * 2;
  const RSI_TOP      = 1140;
  const RSI_H        = 180;
  const VOL_TOP      = 1340;
  const VOL_H        = 120;

  // ── Global fade-in ─────────────────────────────────────────────────────────
  const hudOpacity = interpolate(frame, [F.HUD_IN, F.HUD_DONE], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  // ── Candle draw progress ───────────────────────────────────────────────────
  const chartProgress = interpolate(frame, [F.CHART_START, F.CHART_END], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const visibleCount = Math.max(1, Math.floor(chartProgress * candles.length));

  // ── Price scaling ──────────────────────────────────────────────────────────
  const allPrices = candles.length ? candles.flatMap(c => [c.h, c.l]) : [100, 200];
  const minP = Math.min(...allPrices) * 0.9975;
  const maxP = Math.max(...allPrices) * 1.0025;
  const priceRange = maxP - minP;
  const priceToY = (p) => CHART_H - ((p - minP) / priceRange) * CHART_H;

  const xStep   = candles.length > 0 ? CHART_W / candles.length : CHART_W;
  const candleW = Math.max(5, xStep * 0.55);

  // ── Current price (animated) ───────────────────────────────────────────────
  const currentCandle = candles[Math.min(visibleCount - 1, candles.length - 1)];
  const currentPrice  = currentCandle ? currentCandle.c : 0;

  // ── Support/resistance opacity ─────────────────────────────────────────────
  const srOpacity = interpolate(frame, [F.RSI_START, F.RSI_START + 60], [0, 0.7], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: `linear-gradient(165deg, ${bgGradientStart} 0%, ${bgGradientEnd} 100%)`, fontFamily: "Arial, sans-serif" }}>
      {/* Atmospheric grain */}
      {grain > 0 && (
        <AbsoluteFill style={{ mixBlendMode: "overlay", opacity: grain, pointerEvents: "none" }}>
          <svg width="100%" height="100%" style={{ position: "absolute", top: 0, left: 0 }}>
            <defs>
              <filter id="tc_grain">
                <feTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" stitchTiles="stitch"/>
                <feColorMatrix type="saturate" values="0"/>
              </filter>
            </defs>
            <rect width="100%" height="100%" filter="url(#tc_grain)"/>
          </svg>
        </AbsoluteFill>
      )}
      {/* Vignette */}
      {vignette > 0 && (
        <AbsoluteFill style={{
          background: `radial-gradient(ellipse at 50% 45%, transparent 30%, rgba(0,0,0,${vignette}) 100%)`,
          pointerEvents: "none",
        }}/>
      )}
      <DigitalGrid opacity={0.025} color={hudColor}/>
      <ScanLine color={hudColor} speed={0.3} opacity={0.06}/>

      {/* ── Top HUD: ticker + signal + price ─────────────────────────────── */}
      <div style={{ position: "absolute", top: 40, left: PAD, right: PAD, opacity: hudOpacity }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          {/* Left: ticker + price */}
          <div>
            <div style={{ color: hudColor, fontSize: 18, letterSpacing: 4, fontWeight: 600 }}>NACARTHA AI</div>
            <div style={{ color: "#ffffff", fontSize: 72, fontWeight: 900, lineHeight: 1 }}>{ticker}</div>
            <div style={{ color: "#f59e0b", fontSize: 34, fontWeight: 700, marginTop: 4 }}>
              ${currentPrice.toFixed(2)}
            </div>
          </div>
          {/* Right: signal badge */}
          <div style={{ textAlign: "right", marginTop: 8 }}>
            <SignalBadge direction={direction} startFrame={F.SIGNAL_IN}/>
          </div>
        </div>

        {/* Confidence meter */}
        <div style={{ marginTop: 20 }}>
          <ConfidenceMeter score={score} startFrame={F.CONF_IN} color="#f59e0b" label="AI SIGNAL CONFIDENCE"/>
        </div>
      </div>

      {/* ── Divider ──────────────────────────────────────────────────────── */}
      <div style={{
        position: "absolute", top: CHART_TOP - 10, left: PAD, right: PAD, height: 1,
        background: `linear-gradient(90deg, transparent, ${hudColor}44, transparent)`,
        opacity: hudOpacity,
      }}/>

      {/* ── Main candlestick chart ────────────────────────────────────────── */}
      <svg
        style={{ position: "absolute", left: PAD, top: CHART_TOP, overflow: "visible" }}
        width={CHART_W} height={CHART_H}
      >
        <defs>
          <filter id="glow">
            <feGaussianBlur stdDeviation="4" result="blur"/>
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
        </defs>

        {/* Support line */}
        {support > 0 && srOpacity > 0 && (
          <g opacity={srOpacity}>
            <line x1={0} y1={priceToY(support)} x2={CHART_W} y2={priceToY(support)}
              stroke="#22c55e" strokeWidth={1.5} strokeDasharray="8,6"/>
            <text x={CHART_W - 4} y={priceToY(support) - 6} textAnchor="end"
              fill="#22c55e" fontSize={14}>SUPPORT {support.toFixed(0)}</text>
          </g>
        )}

        {/* Resistance line */}
        {resistance > 0 && srOpacity > 0 && (
          <g opacity={srOpacity}>
            <line x1={0} y1={priceToY(resistance)} x2={CHART_W} y2={priceToY(resistance)}
              stroke="#ef4444" strokeWidth={1.5} strokeDasharray="8,6"/>
            <text x={CHART_W - 4} y={priceToY(resistance) - 6} textAnchor="end"
              fill="#ef4444" fontSize={14}>RESISTANCE {resistance.toFixed(0)}</text>
          </g>
        )}

        {/* Candlesticks */}
        {candles.length > 0 && (
          <Candles
            candles={candles} visibleCount={visibleCount}
            priceToY={priceToY} xStep={xStep} candleW={candleW}
            entryIdx={entryIdx} exitIdx={exitIdx}
          />
        )}

        {/* Price axis labels */}
        {[0.2, 0.4, 0.6, 0.8].map(frac => {
          const p = minP + frac * priceRange;
          const y = priceToY(p);
          return (
            <g key={frac} opacity={0.4}>
              <line x1={0} y1={y} x2={CHART_W} y2={y} stroke="#ffffff" strokeWidth={0.5} strokeDasharray="2,8"/>
              <text x={-4} y={y + 4} textAnchor="end" fill="#ffffff" fontSize={13}>{p.toFixed(0)}</text>
            </g>
          );
        })}
      </svg>

      {/* P&L callout */}
      {exitIdx < candles.length && (
        <PnLCallout
          pnl={pnl}
          x={PAD + exitIdx * xStep + xStep * 0.5 + 20}
          y={CHART_TOP + priceToY(candles[exitIdx]?.l ?? 0) + 50}
          startFrame={F.PNL_IN}
        />
      )}

      {/* ── RSI panel ────────────────────────────────────────────────────── */}
      <div style={{
        position: "absolute", left: PAD, top: RSI_TOP, right: PAD,
        opacity: interpolate(frame, [F.RSI_START, F.RSI_START + 30], [0, 1], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp",
        }),
      }}>
        <div style={{ color: "#888", fontSize: 14, letterSpacing: 3, marginBottom: 6 }}>RSI (14)</div>
        <svg width={CHART_W} height={RSI_H} style={{ overflow: "visible" }}>
          <RSILine rsi={rsi} visibleCount={visibleCount} rsiW={CHART_W} rsiH={RSI_H}/>
        </svg>
      </div>

      {/* ── Volume bars ──────────────────────────────────────────────────── */}
      <div style={{
        position: "absolute", left: PAD, top: VOL_TOP, right: PAD,
        opacity: interpolate(frame, [F.RSI_START + 30, F.RSI_START + 60], [0, 1], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp",
        }),
      }}>
        <div style={{ color: "#888", fontSize: 14, letterSpacing: 3, marginBottom: 4 }}>VOLUME</div>
        <svg width={CHART_W} height={VOL_H}>
          {candles.length > 0 && (
            <VolumeBars candles={candles} visibleCount={visibleCount} volW={CHART_W} volH={VOL_H}/>
          )}
        </svg>
      </div>

      {/* ── Bottom info bar ───────────────────────────────────────────────── */}
      <div style={{
        position: "absolute", bottom: 64, left: PAD, right: PAD,
        opacity: interpolate(frame, [F.WIN_IN, F.WIN_IN + 30], [0, 1], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp",
        }),
        display: "flex", gap: 12, flexWrap: "wrap",
      }}>
        <ScoreChip score={strategy.toUpperCase()} label="STRATEGY" color="#a78bfa" startFrame={F.WIN_IN}/>
        <ScoreChip score={`${score}/100`} label="AI SCORE" color="#f59e0b" startFrame={F.WIN_IN + 10}/>
        <ScoreChip score={direction} label="DIRECTION" color={direction === "SHORT" ? "#ef4444" : "#22c55e"} startFrame={F.WIN_IN + 20}/>
      </div>

      <BrandBar label="NacArtha AI Lab"/>
    </AbsoluteFill>
  );
};

module.exports = { TradingChart };
