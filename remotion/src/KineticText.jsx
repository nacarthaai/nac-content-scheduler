const { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, spring } = require("remotion");

// ── Shared: Film Grain SVG ────────────────────────────────────────────────────
const FilmGrain = ({ opacity = 0.3, id = "grain" }) => (
  <AbsoluteFill style={{ mixBlendMode: "overlay", opacity, pointerEvents: "none" }}>
    <svg width="100%" height="100%" style={{ position: "absolute", top: 0, left: 0 }}>
      <defs>
        <filter id={id}>
          <feTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" stitchTiles="stitch"/>
          <feColorMatrix type="saturate" values="0"/>
        </filter>
      </defs>
      <rect width="100%" height="100%" filter={`url(#${id})`}/>
    </svg>
  </AbsoluteFill>
);

// ── Shared: Vignette ─────────────────────────────────────────────────────────
const Vignette = ({ strength = 0.5 }) => (
  <AbsoluteFill style={{
    background: `radial-gradient(ellipse at 50% 45%, transparent 30%, rgba(0,0,0,${strength}) 100%)`,
    pointerEvents: "none",
  }}/>
);

// ── Shared: Atmos Bg ─────────────────────────────────────────────────────────
const AtmosBg = ({ start = "#0a0a1a", end = "#000000" }) => (
  <AbsoluteFill style={{ background: `linear-gradient(165deg, ${start} 0%, ${end} 100%)` }}/>
);

// ── FilmCard — Cinematic hook ─────────────────────────────────────────────────
// Used for: cinematic_overlay, character_moment, news_break, investigation, confession, split_tension
const FilmCard = ({
  text = "THE AI KNEW",
  subtext = "",
  fontSize = 100,
  colorPrimary = "#f59e0b",
  colorSecondary = "#ffffff",
  bgGradientStart = "#0a0a1a",
  bgGradientEnd = "#000000",
  typography = "ultra_heavy",
  animation = "slam",
  grain = 0.3,
  vignette = 0.5,
  textPosition = "left",
  layout = "cinematic_overlay",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const words = String(text).split(" ").filter(Boolean);

  // Per-word spring animations — each word slams/flows in staggered
  const wordDelay   = animation === "slow_burn" ? 14 : animation === "glitch" ? 6 : 8;
  const springCfg   = animation === "slam"       ? { damping: 9, mass: 0.9 }
                    : animation === "slow_burn"  ? { damping: 22 }
                    : animation === "glitch"     ? { damping: 7, mass: 1.4 }
                    :                              { damping: 13 };

  const typeFamilies = {
    ultra_heavy: "Arial Black, Impact, 'Haettenschweiler', sans-serif",
    editorial:   "'Georgia', 'Times New Roman', serif",
    condensed:   "Impact, 'Arial Narrow', Arial Black, sans-serif",
    explosive:   "Arial Black, Impact, sans-serif",
    minimal:     "'Helvetica Neue', Helvetica, Arial, sans-serif",
  };
  const fontFamily = typeFamilies[typography] || typeFamilies.ultra_heavy;
  const fontWeight = typography === "editorial" || typography === "minimal" ? 300 : 900;
  const letterSpacing = typography === "editorial" ? 3
    : typography === "minimal"  ? 6
    : typography === "condensed" ? -4
    : -2;
  const actualFontSize = typography === "explosive" ? fontSize * 1.15 : fontSize;
  const textTransform = (typography === "editorial" || typography === "minimal") ? "none" : "uppercase";

  // Text alignment
  const alignItems   = textPosition === "center" ? "center"
    : textPosition === "right" ? "flex-end" : "flex-start";
  const textAlign    = textPosition;
  const padLeft      = textPosition === "center" ? 60 : 80;

  return (
    <AbsoluteFill>
      <AtmosBg start={bgGradientStart} end={bgGradientEnd}/>

      {/* Ambient color glow — positions based on text side */}
      <div style={{
        position: "absolute",
        left: textPosition === "right" ? "auto" : -60,
        right: textPosition === "right" ? -60 : "auto",
        top: "20%",
        width: 500, height: 700, borderRadius: "50%",
        background: `radial-gradient(circle, ${colorPrimary}1a 0%, transparent 70%)`,
        filter: "blur(80px)",
      }}/>

      <FilmGrain opacity={grain} id="fc_grain"/>
      <Vignette strength={vignette}/>

      {/* Word-by-word text */}
      <AbsoluteFill style={{ justifyContent: "center", alignItems, paddingLeft: padLeft, paddingRight: 60 }}>
        <div style={{ textAlign }}>
          {words.map((word, i) => {
            const startFrame = i * wordDelay;
            const prog = spring({ frame: frame - startFrame, fps,
              from: 0, to: 1, durationInFrames: 18, config: springCfg });

            const translateY = interpolate(prog, [0, 1],
              animation === "slow_burn" ? [20, 0] : [90, 0]);
            const opacity = interpolate(frame - startFrame, [0, animation === "slow_burn" ? 14 : 7], [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

            // Glitch: chromatic shift on odd frames for early words
            const glitchX = (animation === "glitch" && frame < startFrame + 12)
              ? interpolate(frame % 6, [0,2,4,6], [0,3,-2,0]) : 0;

            // Last word gets accent color for emphasis
            const wordColor = (i === words.length - 1 && animation === "slam")
              ? colorPrimary : (colorSecondary || "#ffffff");

            return (
              <span key={i} style={{ display: "inline-block", marginRight: actualFontSize * 0.12 }}>
                <span style={{
                  display: "block",
                  transform: `translateY(${translateY}px) translateX(${glitchX}px)`,
                  opacity,
                  fontFamily,
                  fontSize: actualFontSize,
                  fontWeight,
                  textTransform,
                  letterSpacing,
                  lineHeight: 0.92,
                  color: wordColor,
                  textShadow: `0 4px 40px ${colorPrimary}44`,
                }}>{word}</span>
              </span>
            );
          })}

          {/* Subtext */}
          {subtext ? (
            <div style={{
              display: "block",
              color: `${colorPrimary}cc`,
              fontSize: actualFontSize * 0.27,
              fontWeight: typography === "editorial" ? 300 : 500,
              fontFamily,
              letterSpacing: typography === "editorial" ? 5 : 2,
              textTransform: "uppercase",
              marginTop: actualFontSize * 0.18,
              opacity: interpolate(frame, [words.length * wordDelay + 8, words.length * wordDelay + 22], [0, 1],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
            }}>{subtext}</div>
          ) : null}
        </div>
      </AbsoluteFill>

      {/* Accent line — grows in from left/center */}
      <div style={{
        position: "absolute", bottom: 90,
        left: textPosition === "center" ? "15%" : 80,
        height: 3,
        width: interpolate(frame, [words.length * wordDelay + 5, words.length * wordDelay + 35],
          [0, textPosition === "center" ? 780 : 240], { extrapolateRight: "clamp" }),
        background: `linear-gradient(90deg, ${colorPrimary}, ${colorPrimary}00)`,
        boxShadow: `0 0 16px ${colorPrimary}88`,
      }}/>
    </AbsoluteFill>
  );
};

// ── TypoSlam — Word-by-word slam impact ──────────────────────────────────────
// Used for: typo_slam layout
const TypoSlam = ({
  text = "THE AI KNEW",
  subtext = "",
  fontSize = 110,
  colorPrimary = "#ef4444",
  colorSecondary = "#ffffff",
  bgGradientStart = "#0d0000",
  bgGradientEnd = "#000000",
  typography = "explosive",
  animation = "slam",
  grain = 0.45,
  vignette = 0.65,
  textPosition = "center",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const words = String(text).split(" ").filter(Boolean);

  return (
    <AbsoluteFill>
      <AtmosBg start={bgGradientStart} end={bgGradientEnd}/>
      <FilmGrain opacity={grain * 1.4} id="ts_grain"/>
      <Vignette strength={vignette}/>

      {/* Central color burst */}
      <div style={{
        position: "absolute", top: "30%", left: "10%",
        width: 800, height: 800, borderRadius: "50%",
        background: `radial-gradient(circle, ${colorPrimary}12 0%, transparent 65%)`,
        filter: "blur(60px)",
      }}/>

      {/* Stacked words — each on its own line, slamming in */}
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div style={{ textAlign: "center", width: "100%", padding: "0 50px" }}>
          {words.map((word, i) => {
            const startF = i * 10;
            const scale = spring({ frame: frame - startF, fps,
              from: 1.7, to: 1, durationInFrames: 14, config: { damping: 7, mass: 1.3 } });
            const opacity = interpolate(frame - startF, [0, 5], [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const blur = interpolate(frame - startF, [0, 8], [6, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

            // Alternate color for visual rhythm
            const col = i % 2 === 0 ? (colorSecondary || "#ffffff") : colorPrimary;

            return (
              <div key={i} style={{
                display: "block",
                transform: `scale(${scale})`,
                opacity,
                filter: `blur(${blur}px)`,
                fontFamily: "Arial Black, Impact, 'Haettenschweiler', sans-serif",
                fontSize,
                fontWeight: 900,
                textTransform: "uppercase",
                letterSpacing: -5,
                lineHeight: 0.86,
                color: col,
                textShadow: `0 0 80px ${colorPrimary}44`,
              }}>{word}</div>
            );
          })}

          {subtext ? (
            <div style={{
              color: `${colorPrimary}bb`,
              fontSize: fontSize * 0.24,
              fontWeight: 500,
              letterSpacing: 4,
              textTransform: "uppercase",
              marginTop: fontSize * 0.3,
              opacity: interpolate(frame, [words.length * 10 + 10, words.length * 10 + 24], [0, 1],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
            }}>{subtext}</div>
          ) : null}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ── ImpactStat — Dramatic P&L reveal with counter ────────────────────────────
const ImpactStat = ({
  ticker = "TSLA",
  direction = "SHORT",
  score = 65,
  pnl = -50,
  colorPrimary = "#f59e0b",
  colorSecondary = "#ffffff",
  bgGradientStart,
  bgGradientEnd,
  typography = "ultra_heavy",
  animation = "slam",
  grain = 0.3,
  vignette = 0.55,
  textPosition = "left",
  layout = "cinematic_overlay",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const isShort  = direction === "SHORT";
  const isLoss   = pnl < 0;
  const dirColor = isShort ? "#ef4444" : "#22c55e";
  const pnlColor = isLoss  ? "#ef4444" : "#22c55e";
  const pnlSign  = pnl > 0 ? "+" : "";
  const absPnl   = Math.abs(pnl);

  // Use direction-appropriate bg if AI didn't set one
  const bgStart = bgGradientStart || (isShort ? "#180000" : "#001408");
  const bgEnd   = bgGradientEnd   || "#000000";

  // P&L counter: counts up over 50 frames then slams to final value
  const counterProg = interpolate(frame, [0, 50], [0, 1], { extrapolateRight: "clamp" });
  const displayPnl  = Math.round(counterProg * absPnl);

  // Impact: number scale slam at frame 50
  const numberSlam = spring({ frame: frame - 50, fps,
    from: 1.4, to: 1, durationInFrames: 12, config: { damping: 7 } });
  const numberScale = frame >= 50 ? numberSlam : 1;

  // Badge slides in from the side
  const badgeSlide = spring({ frame: frame - 5, fps,
    from: textPosition === "left" ? -600 : 600, to: 0,
    durationInFrames: 22, config: { damping: 12 } });

  // Score fades in late
  const scoreOpacity = interpolate(frame, [60, 78], [0, 1], { extrapolateRight: "clamp" });

  const pnlFontSize = absPnl >= 10000 ? 110 : absPnl >= 1000 ? 130 : 155;

  return (
    <AbsoluteFill>
      <AtmosBg start={bgStart} end={bgEnd}/>

      {/* Color glow behind the number */}
      <div style={{
        position: "absolute", top: "25%",
        left: textPosition === "left" ? 0 : "auto",
        right: textPosition === "right" ? 0 : "auto",
        width: 700, height: 700, borderRadius: "50%",
        background: `radial-gradient(circle, ${pnlColor}18 0%, transparent 70%)`,
        filter: "blur(60px)",
      }}/>

      <FilmGrain opacity={grain} id="is_grain"/>
      <Vignette strength={vignette}/>

      <AbsoluteFill style={{ justifyContent: "center", alignItems: "flex-start", padding: "0 80px" }}>
        {/* Ticker + direction badge row */}
        <div style={{
          transform: `translateX(${badgeSlide}px)`,
          display: "flex", alignItems: "center", gap: 20, marginBottom: 20,
        }}>
          <span style={{
            color: "#ffffff", fontSize: 36, fontWeight: 900,
            fontFamily: "Arial Black, sans-serif", letterSpacing: 3,
          }}>{ticker}</span>
          <div style={{
            background: dirColor,
            color: "#ffffff",
            fontFamily: "Arial Black, sans-serif",
            fontSize: 22, fontWeight: 900,
            letterSpacing: 4, padding: "6px 22px",
            boxShadow: `0 0 24px ${dirColor}88`,
          }}>{direction}</div>
        </div>

        {/* Huge P&L counter */}
        <div style={{ transform: `scale(${numberScale})`, transformOrigin: "left center" }}>
          <div style={{
            fontFamily: "Arial Black, Impact, sans-serif",
            fontSize: pnlFontSize,
            fontWeight: 900,
            color: pnlColor,
            lineHeight: 0.85,
            letterSpacing: -6,
            textShadow: `0 0 80px ${pnlColor}55, 0 10px 0 rgba(0,0,0,0.4)`,
          }}>
            {pnlSign}${displayPnl}
          </div>
        </div>

        {/* Label */}
        <div style={{
          color: "rgba(255,255,255,0.45)",
          fontSize: 26, fontWeight: 400,
          letterSpacing: 7, marginTop: 14,
          opacity: interpolate(frame, [25, 40], [0, 1], { extrapolateRight: "clamp" }),
        }}>REALIZED P&L</div>

        {/* AI Score strip */}
        <div style={{
          marginTop: 44, display: "flex", alignItems: "center", gap: 18,
          opacity: scoreOpacity,
        }}>
          <div style={{
            width: 4, height: 44,
            background: colorPrimary,
            boxShadow: `0 0 14px ${colorPrimary}`,
          }}/>
          <div>
            <div style={{ color: "rgba(255,255,255,0.4)", fontSize: 18, letterSpacing: 4 }}>AI SIGNAL</div>
            <div style={{
              color: colorPrimary,
              fontSize: 38, fontWeight: 900,
              fontFamily: "Arial Black, sans-serif",
              letterSpacing: 2,
            }}>{score}/100</div>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ── CTACard — updated to accept new vis spec ──────────────────────────────────
const CTACard = ({
  handle = "@nacartha",
  // New spec props
  colorPrimary = "#f59e0b",
  colorSecondary = "#ffffff",
  bgGradientStart = "#0a0a1a",
  bgGradientEnd = "#000000",
  typography = "ultra_heavy",
  animation = "slam",
  grain = 0.3,
  vignette = 0.4,
  textPosition = "center",
  layout = "cinematic_overlay",
  // Legacy theme prop fallback
  theme,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Resolve from legacy theme if present
  const accentColor = (theme && theme.accent) ? theme.accent : colorPrimary;
  const bgStart     = bgGradientStart || (theme && theme.bg) || "#0a0a1a";
  const bgEnd       = bgGradientEnd   || "#000000";

  const scale   = spring({ frame, fps, from: 0.8, to: 1,
    durationInFrames: 22, config: { damping: 12 } });
  const opacity = interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" });
  const pulse   = interpolate(frame % 40, [0, 20, 40], [1, 1.04, 1]);
  const lineW   = interpolate(frame, [20, 50], [0, 320], { extrapolateRight: "clamp" });

  const fontFamily = typography === "editorial"
    ? "Georgia, serif"
    : "Arial Black, Impact, sans-serif";

  return (
    <AbsoluteFill>
      <AtmosBg start={bgStart} end={bgEnd}/>
      <FilmGrain opacity={grain} id="cta_grain"/>
      <Vignette strength={vignette}/>

      {/* Central glow */}
      <div style={{
        position: "absolute", top: "30%", left: "15%",
        width: 600, height: 600, borderRadius: "50%",
        background: `radial-gradient(circle, ${accentColor}18 0%, transparent 70%)`,
        filter: "blur(60px)",
      }}/>

      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div style={{ transform: `scale(${scale})`, opacity, textAlign: "center" }}>
          <div style={{
            color: "rgba(255,255,255,0.5)",
            fontSize: 22, letterSpacing: 8,
            fontFamily,
            marginBottom: 24,
          }}>FOLLOW FOR DAILY AI TRADES</div>

          <div style={{
            fontFamily: "Arial Black, Impact, sans-serif",
            fontSize: 72, fontWeight: 900,
            color: accentColor,
            letterSpacing: -2,
            textShadow: `0 0 60px ${accentColor}66`,
            transform: `scale(${pulse})`,
          }}>{handle}</div>

          {/* Accent line */}
          <div style={{
            height: 3, width: lineW,
            background: `linear-gradient(90deg, transparent, ${accentColor}, transparent)`,
            margin: "24px auto 0",
            boxShadow: `0 0 16px ${accentColor}88`,
          }}/>

          <div style={{
            color: "rgba(255,255,255,0.35)",
            fontSize: 24, marginTop: 24,
            letterSpacing: 2,
            opacity: interpolate(frame, [18, 32], [0, 1], { extrapolateRight: "clamp" }),
          }}>Real AI. Real Trades. Every Day.</div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ── GlitchHook — chromatic aberration, data-corruption aesthetic ─────────────
const GlitchHook = ({
  text = "THE AI KNEW",
  subtext = "",
  colorPrimary = "#a855f7",
  bgGradientStart = "#04040c",
  bgGradientEnd = "#000000",
  grain = 0.4,
  vignette = 0.6,
  textPosition = "center",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const words = String(text).split(" ").filter(Boolean);

  // Glitch offset cycles
  const glitchR  = interpolate(frame % 7, [0,2,4,7], [0, 6, -4, 0]);
  const glitchB  = interpolate(frame % 7, [0,2,4,7], [0, -4, 6, 0]);
  const scanY    = interpolate(frame % 60, [0, 60], [0, 1920]);
  const settle   = Math.min(frame / 30, 1);
  const glitchAmt = (1 - settle) * 12 + (frame % 9 < 2 ? 8 : 0); // residual glitch

  const containerOpacity = interpolate(frame, [0, 5], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ opacity: containerOpacity }}>
      <AtmosBg start={bgGradientStart} end={bgGradientEnd}/>
      <FilmGrain opacity={grain * 1.5} id="gh_grain"/>

      {/* Scan bar moving down */}
      <div style={{
        position: "absolute", left: 0, right: 0,
        top: scanY, height: 3,
        background: `linear-gradient(90deg, transparent, ${colorPrimary}66, transparent)`,
      }}/>

      {/* Vignette */}
      <Vignette strength={vignette}/>

      {/* RGB split: render text 3 times with color offsets */}
      {[
        { color: "#ff003c", x: -glitchAmt, y: 0, blend: "screen", op: 0.6 },
        { color: "#00ffff", x:  glitchAmt, y: 0, blend: "screen", op: 0.6 },
        { color: "#ffffff", x:  0,         y: 0, blend: "normal",  op: 1.0 },
      ].map(({ color, x, y, blend, op }, pass) => (
        <AbsoluteFill key={pass}
          style={{ mixBlendMode: blend, opacity: op,
            justifyContent: "center", alignItems: "center" }}>
          <div style={{
            transform: `translate(${x}px, ${y}px)`,
            textAlign: "center", padding: "0 60px",
          }}>
            {words.map((word, i) => {
              const startF = i * 6;
              const p = spring({ frame: frame - startF, fps, from: 0, to: 1,
                durationInFrames: 14, config: { damping: 7, mass: 1.2 } });
              const vy = interpolate(p, [0, 1], [60, 0]);
              const op2 = interpolate(frame - startF, [0, 4], [0, 1],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
              return (
                <span key={i} style={{ display: "inline-block", marginRight: 18 }}>
                  <span style={{
                    display: "block",
                    transform: `translateY(${vy}px)`,
                    opacity: op2,
                    color,
                    fontFamily: "Arial Black, Impact, sans-serif",
                    fontSize: 88,
                    fontWeight: 900,
                    textTransform: "uppercase",
                    letterSpacing: -3,
                    lineHeight: 0.92,
                  }}>{word}</span>
                </span>
              );
            })}
            {subtext && pass === 2 && (
              <div style={{
                color: `${colorPrimary}cc`, fontSize: 26, fontWeight: 500,
                letterSpacing: 4, textTransform: "uppercase", marginTop: 20,
                opacity: interpolate(frame, [words.length * 6 + 10, words.length * 6 + 24], [0, 1],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
              }}>{subtext}</div>
            )}
          </div>
        </AbsoluteFill>
      ))}

      {/* Noise blocks on glitch frames */}
      {frame % 9 < 2 && [0.2, 0.55, 0.75].map((pct, i) => (
        <div key={i} style={{
          position: "absolute", top: `${pct * 100}%`,
          left: 0, right: 0, height: 6,
          background: i % 2 === 0 ? "#ff003c" : "#00ffff", opacity: 0.4,
        }}/>
      ))}

      {/* Bottom accent */}
      <div style={{
        position: "absolute", bottom: 80, left: "10%",
        height: 2, width: interpolate(frame, [30, 60], [0, 800], { extrapolateRight: "clamp" }),
        background: `linear-gradient(90deg, transparent, ${colorPrimary}, transparent)`,
        boxShadow: `0 0 20px ${colorPrimary}88`,
      }}/>
    </AbsoluteFill>
  );
};

// ── SplitReveal — vertical split: ticker+direction left, hook text right ──────
const SplitReveal = ({
  text = "THE AI KNEW",
  subtext = "",
  ticker = "TSLA",
  direction = "SHORT",
  colorPrimary = "#ef4444",
  bgGradientStart = "#0a0000",
  bgGradientEnd = "#000000",
  grain = 0.32,
  vignette = 0.5,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const dirColor    = direction === "SHORT" ? "#ef4444" : "#22c55e";
  const lineX       = interpolate(frame, [0, 20], [-1080, 540], { extrapolateRight: "clamp" });
  const leftOpacity = interpolate(frame, [20, 35], [0, 1], { extrapolateRight: "clamp" });
  const rightOpacity = interpolate(frame, [30, 45], [0, 1], { extrapolateRight: "clamp" });

  const words = String(text).split(" ").filter(Boolean);

  return (
    <AbsoluteFill>
      <AtmosBg start={bgGradientStart} end={bgGradientEnd}/>
      <FilmGrain opacity={grain} id="sr_grain"/>
      <Vignette strength={vignette}/>

      {/* Glowing divider line — sweeps down from top */}
      <div style={{
        position: "absolute", left: lineX, top: 0, bottom: 0, width: 3,
        background: `linear-gradient(180deg, transparent, ${colorPrimary}, transparent)`,
        boxShadow: `0 0 30px ${colorPrimary}`,
      }}/>

      {/* Left panel — ticker + direction */}
      <div style={{
        position: "absolute", left: 0, top: 0, bottom: 0, width: 520,
        display: "flex", flexDirection: "column",
        justifyContent: "center", alignItems: "center",
        opacity: leftOpacity,
      }}>
        <div style={{
          color: "#ffffff", fontSize: 80, fontWeight: 900,
          fontFamily: "Arial Black, sans-serif",
          letterSpacing: -2, lineHeight: 1,
        }}>{ticker}</div>
        <div style={{
          background: dirColor, color: "#ffffff",
          fontFamily: "Arial Black, sans-serif",
          fontSize: 32, fontWeight: 900, letterSpacing: 6,
          padding: "8px 28px", marginTop: 16,
          boxShadow: `0 0 30px ${dirColor}88`,
        }}>{direction}</div>
      </div>

      {/* Right panel — hook text */}
      <div style={{
        position: "absolute", left: 560, right: 0, top: 0, bottom: 0,
        display: "flex", flexDirection: "column",
        justifyContent: "center", padding: "0 50px 0 30px",
        opacity: rightOpacity,
      }}>
        {words.map((word, i) => {
          const sF = i * 8 + 30;
          const p = spring({ frame: frame - sF, fps, from: 0, to: 1,
            durationInFrames: 16, config: { damping: 11 } });
          const tx = interpolate(p, [0, 1], [80, 0]);
          const op = interpolate(frame - sF, [0, 8], [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const isLast = i === words.length - 1;
          return (
            <div key={i} style={{
              transform: `translateX(${tx}px)`, opacity: op,
              color: isLast ? colorPrimary : "#ffffff",
              fontFamily: "Arial Black, sans-serif",
              fontSize: 56, fontWeight: 900,
              textTransform: "uppercase",
              letterSpacing: -2, lineHeight: 1.1,
            }}>{word}</div>
          );
        })}
        {subtext && (
          <div style={{
            color: `rgba(255,255,255,0.5)`, fontSize: 22,
            letterSpacing: 3, marginTop: 20, textTransform: "uppercase",
            opacity: interpolate(frame, [words.length * 8 + 38, words.length * 8 + 52], [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
          }}>{subtext}</div>
        )}
      </div>
    </AbsoluteFill>
  );
};

// ── WordPunch — single key word punches from center, then supporting text ──────
const WordPunch = ({
  text = "WRONG",
  subtext = "",
  supportText = "",
  colorPrimary = "#f59e0b",
  bgGradientStart = "#080400",
  bgGradientEnd = "#000000",
  grain = 0.38,
  vignette = 0.6,
  textPosition = "center",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const words = String(text).split(" ").filter(Boolean);
  const punchWord = words[0] || "WRONG";
  const restWords = words.slice(1);

  // Punch: scale from 4x down to 1x with overshoot
  const punchScale = spring({ frame, fps, from: 4, to: 1,
    durationInFrames: 22, config: { damping: 7, mass: 0.7 } });
  const punchOpacity = interpolate(frame, [0, 3], [0, 1], { extrapolateRight: "clamp" });

  // Rest words fade in after punch settles
  const restOpacity = interpolate(frame, [25, 40], [0, 1], { extrapolateRight: "clamp" });
  const restSlide   = interpolate(frame, [25, 40], [30, 0], { extrapolateRight: "clamp" });

  // Subtext
  const subOpacity = interpolate(frame, [40, 55], [0, 1], { extrapolateRight: "clamp" });

  // Glow pulse after impact
  const glow = frame > 20
    ? interpolate(frame % 30, [0, 15, 30], [0.4, 1, 0.4])
    : 0;

  return (
    <AbsoluteFill>
      <AtmosBg start={bgGradientStart} end={bgGradientEnd}/>
      <FilmGrain opacity={grain} id="wp_grain"/>

      {/* Expanding ring on impact */}
      {frame > 0 && frame < 40 && (
        <div style={{
          position: "absolute", top: "40%", left: "50%",
          width: frame * 40, height: frame * 40, borderRadius: "50%",
          border: `2px solid ${colorPrimary}`,
          transform: "translate(-50%, -50%)",
          opacity: interpolate(frame, [0, 40], [0.8, 0]),
        }}/>
      )}

      <Vignette strength={vignette}/>

      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div style={{ textAlign: "center", padding: "0 60px" }}>
          {/* The punch word */}
          <div style={{
            transform: `scale(${punchScale})`,
            opacity: punchOpacity,
            display: "block",
            fontFamily: "Arial Black, Impact, sans-serif",
            fontSize: 140,
            fontWeight: 900,
            textTransform: "uppercase",
            letterSpacing: -8,
            lineHeight: 0.88,
            color: colorPrimary,
            textShadow: `0 0 ${80 * glow}px ${colorPrimary}88`,
          }}>{punchWord}</div>

          {/* Rest of words slide in below */}
          {restWords.length > 0 && (
            <div style={{
              opacity: restOpacity,
              transform: `translateY(${restSlide}px)`,
              color: "#ffffff",
              fontFamily: "Arial Black, sans-serif",
              fontSize: 68,
              fontWeight: 900,
              textTransform: "uppercase",
              letterSpacing: -3,
              lineHeight: 1,
              marginTop: 16,
            }}>{restWords.join(" ")}</div>
          )}

          {/* Subtext */}
          {subtext && (
            <div style={{
              opacity: subOpacity,
              color: `${colorPrimary}cc`,
              fontSize: 24, letterSpacing: 5,
              textTransform: "uppercase", marginTop: 28,
              fontWeight: 500,
            }}>{subtext}</div>
          )}
        </div>
      </AbsoluteFill>

      {/* Bottom line */}
      <div style={{
        position: "absolute", bottom: 80, left: "20%",
        height: 3,
        width: interpolate(frame, [22, 55], [0, 600], { extrapolateRight: "clamp" }),
        background: `linear-gradient(90deg, transparent, ${colorPrimary}, transparent)`,
        boxShadow: `0 0 20px ${colorPrimary}66`,
      }}/>
    </AbsoluteFill>
  );
};

// ── NewsFlash — breaking news bar + urgent headline ───────────────────────────
const NewsFlash = ({
  text = "AI SIGNALS SHORT",
  subtext = "",
  ticker = "TSLA",
  direction = "SHORT",
  colorPrimary = "#ef4444",
  bgGradientStart = "#070002",
  bgGradientEnd = "#000000",
  grain = 0.3,
  vignette = 0.55,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const barSlide   = interpolate(frame, [0, 16], [-1080, 0], { extrapolateRight: "clamp" });
  const textOpacity = interpolate(frame, [20, 32], [0, 1], { extrapolateRight: "clamp" });
  const textSlide  = interpolate(frame, [20, 32], [60, 0], { extrapolateRight: "clamp" });
  const tickerSlide = interpolate(frame, [8, 22], [1080, 0], { extrapolateRight: "clamp" });
  const subOpacity = interpolate(frame, [35, 48], [0, 1], { extrapolateRight: "clamp" });

  const tickerText = `BREAKING · ${ticker} ${direction} · NACARTHA AI · LIVE SIGNAL ·`;
  const scrollX = interpolate(frame, [8, 90], [0, -800], { extrapolateLeft: "clamp" });

  return (
    <AbsoluteFill>
      <AtmosBg start={bgGradientStart} end={bgGradientEnd}/>
      <FilmGrain opacity={grain} id="nf_grain"/>
      <Vignette strength={vignette}/>

      {/* Top: "BREAKING" label bar */}
      <div style={{
        position: "absolute", top: 120, left: 0, right: 0,
        transform: `translateX(${barSlide}px)`,
      }}>
        <div style={{ display: "flex", alignItems: "stretch" }}>
          <div style={{
            background: colorPrimary, padding: "12px 32px",
            color: "#ffffff", fontFamily: "Arial Black, sans-serif",
            fontSize: 24, fontWeight: 900, letterSpacing: 6,
            flexShrink: 0,
          }}>BREAKING</div>
          <div style={{
            background: "rgba(255,255,255,0.08)",
            borderTop: `2px solid ${colorPrimary}`,
            borderBottom: `2px solid ${colorPrimary}`,
            flex: 1, display: "flex", alignItems: "center",
            padding: "0 24px",
            overflow: "hidden",
          }}>
            <div style={{
              color: "#ffffff", fontSize: 20, fontWeight: 600, letterSpacing: 2,
              transform: `translateX(${scrollX}px)`,
              whiteSpace: "nowrap",
            }}>{tickerText.repeat(4)}</div>
          </div>
        </div>
      </div>

      {/* Main headline */}
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "flex-start", padding: "0 60px" }}>
        <div style={{
          opacity: textOpacity,
          transform: `translateY(${textSlide}px)`,
        }}>
          <div style={{
            color: "#ffffff",
            fontFamily: "Arial Black, sans-serif",
            fontSize: 82,
            fontWeight: 900,
            textTransform: "uppercase",
            letterSpacing: -3,
            lineHeight: 0.92,
            textShadow: `0 4px 30px rgba(0,0,0,0.8)`,
          }}>{String(text).toUpperCase()}</div>
          {subtext && (
            <div style={{
              color: `${colorPrimary}cc`,
              fontSize: 28, letterSpacing: 3,
              textTransform: "uppercase", marginTop: 20,
              fontWeight: 500,
              opacity: subOpacity,
            }}>{subtext}</div>
          )}
        </div>
      </AbsoluteFill>

      {/* Bottom ticker bar */}
      <div style={{
        position: "absolute", bottom: 80, left: 0, right: 0,
        transform: `translateX(${tickerSlide}px)`,
      }}>
        <div style={{
          background: colorPrimary, height: 52,
          display: "flex", alignItems: "center", paddingLeft: 40,
          overflow: "hidden",
        }}>
          <div style={{
            color: "#ffffff", fontFamily: "Arial Black, sans-serif",
            fontSize: 22, fontWeight: 900, letterSpacing: 4,
            whiteSpace: "nowrap",
            transform: `translateX(${scrollX * 0.5}px)`,
          }}>
            {`NACARTHA AI · ${ticker} ${direction} SIGNAL LIVE · AI SCORE ANALYSIS · `.repeat(3)}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── WinLoseSlam — WIN or LOSS fills screen, then stats reveal ─────────────────
const WinLoseSlam = ({
  ticker = "TSLA",
  direction = "SHORT",
  score = 65,
  pnl = -50,
  colorPrimary = "#f59e0b",
  bgGradientStart,
  bgGradientEnd = "#000000",
  grain = 0.35,
  vignette = 0.6,
  textPosition = "center",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const isWin    = pnl > 0;
  const label    = isWin ? "WIN" : "LOSS";
  const labelCol = isWin ? "#22c55e" : "#ef4444";
  const pnlSign  = pnl > 0 ? "+" : "";
  const absPnl   = Math.abs(pnl);
  const bgStart  = bgGradientStart || (isWin ? "#001a08" : "#1a0000");

  // Phase 1 (frames 0-45): HUGE WIN/LOSS text slams in
  const slamScale = spring({ frame, fps, from: 5, to: 1,
    durationInFrames: 20, config: { damping: 6, mass: 0.8 } });
  const slamOpacity = interpolate(frame, [0, 4], [0, 1], { extrapolateRight: "clamp" });

  // Phase 2 (frames 40+): stats reveal from below
  const statsOpacity = interpolate(frame, [40, 58], [0, 1], { extrapolateRight: "clamp" });
  const statsSlide   = interpolate(frame, [40, 58], [60, 0], { extrapolateRight: "clamp" });

  // P&L counter
  const countProg = interpolate(frame, [40, 85], [0, 1], { extrapolateRight: "clamp" });
  const displayPnl = Math.round(countProg * absPnl);

  // Background color pulse on slam
  const bgPulse = frame < 25
    ? interpolate(frame, [0, 10, 25], [0, 0.15, 0], { extrapolateRight: "clamp" })
    : 0;

  return (
    <AbsoluteFill>
      <AtmosBg start={bgStart} end={bgGradientEnd}/>

      {/* Color flash on slam */}
      <AbsoluteFill style={{ background: labelCol, opacity: bgPulse, pointerEvents: "none" }}/>

      <FilmGrain opacity={grain} id="wl_grain"/>
      <Vignette strength={vignette}/>

      {/* Central glow */}
      <div style={{
        position: "absolute", top: "20%", left: "10%",
        width: 800, height: 800, borderRadius: "50%",
        background: `radial-gradient(circle, ${labelCol}20 0%, transparent 65%)`,
        filter: "blur(60px)",
      }}/>

      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div style={{ textAlign: "center", padding: "0 40px" }}>
          {/* WIN / LOSS slam */}
          <div style={{
            transform: `scale(${slamScale})`, opacity: slamOpacity,
            fontFamily: "Arial Black, Impact, sans-serif",
            fontSize: 180,
            fontWeight: 900,
            letterSpacing: -10,
            lineHeight: 0.85,
            color: labelCol,
            textShadow: `0 0 120px ${labelCol}66, 0 15px 0 rgba(0,0,0,0.5)`,
          }}>{label}</div>

          {/* Stats reveal below */}
          <div style={{
            opacity: statsOpacity,
            transform: `translateY(${statsSlide}px)`,
            marginTop: 32,
          }}>
            {/* Ticker + direction row */}
            <div style={{
              display: "flex", justifyContent: "center",
              alignItems: "center", gap: 20, marginBottom: 16,
            }}>
              <span style={{ color: "#ffffff", fontFamily: "Arial Black, sans-serif",
                fontSize: 40, fontWeight: 900, letterSpacing: 2 }}>{ticker}</span>
              <div style={{
                background: direction === "SHORT" ? "#ef4444" : "#22c55e",
                color: "#fff", fontFamily: "Arial Black, sans-serif",
                fontSize: 22, fontWeight: 900, letterSpacing: 5,
                padding: "5px 20px",
              }}>{direction}</div>
            </div>

            {/* P&L counter */}
            <div style={{
              fontFamily: "Arial Black, sans-serif",
              fontSize: 100, fontWeight: 900,
              color: labelCol, lineHeight: 0.9,
              letterSpacing: -5,
              textShadow: `0 0 40px ${labelCol}55`,
            }}>{pnlSign}${displayPnl}</div>

            {/* AI score */}
            <div style={{
              color: "rgba(255,255,255,0.45)",
              fontSize: 22, letterSpacing: 5, marginTop: 14,
              fontWeight: 400,
            }}>AI SIGNAL SCORE <span style={{ color: colorPrimary }}>{score}</span></div>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ── DataReveal — multiple metrics cascade in rapidly ─────────────────────────
const DataReveal = ({
  ticker = "TSLA",
  direction = "SHORT",
  score = 65,
  pnl = -50,
  colorPrimary = "#00e5ff",
  bgGradientStart = "#020610",
  bgGradientEnd = "#000000",
  grain = 0.28,
  vignette = 0.45,
  textPosition = "left",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const pnlColor = pnl > 0 ? "#22c55e" : "#ef4444";
  const pnlSign  = pnl > 0 ? "+" : "";
  const absPnl   = Math.abs(pnl);
  const dirColor = direction === "SHORT" ? "#ef4444" : "#22c55e";

  const metrics = [
    { label: "TICKER",    value: ticker,                  color: "#ffffff",    size: 90 },
    { label: "DIRECTION", value: direction,               color: dirColor,     size: 64 },
    { label: "P&L",       value: `${pnlSign}$${absPnl}`, color: pnlColor,     size: 80 },
    { label: "AI SCORE",  value: `${score}/100`,          color: colorPrimary, size: 56 },
  ];

  return (
    <AbsoluteFill>
      <AtmosBg start={bgGradientStart} end={bgGradientEnd}/>

      {/* Side accent bar */}
      <div style={{
        position: "absolute", left: 60, top: "10%", bottom: "10%", width: 4,
        background: `linear-gradient(180deg, transparent, ${colorPrimary}, transparent)`,
        boxShadow: `0 0 20px ${colorPrimary}`,
        opacity: interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" }),
      }}/>

      <FilmGrain opacity={grain} id="dr_grain"/>
      <Vignette strength={vignette}/>

      <AbsoluteFill style={{ justifyContent: "center", alignItems: "flex-start", padding: "0 100px" }}>
        <div style={{ width: "100%" }}>
          {metrics.map(({ label, value, color, size }, i) => {
            const startF = i * 16;
            const slideX = interpolate(frame - startF, [0, 18], [-120, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const op = interpolate(frame - startF, [0, 10], [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const lineW = interpolate(frame - startF, [12, 30], [0, 800 - 40],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

            return (
              <div key={i} style={{ marginBottom: 28, transform: `translateX(${slideX}px)`, opacity: op }}>
                <div style={{
                  color: "rgba(255,255,255,0.35)", fontSize: 16,
                  letterSpacing: 6, fontWeight: 500,
                }}>{label}</div>
                <div style={{
                  color, fontFamily: "Arial Black, Impact, sans-serif",
                  fontSize: size, fontWeight: 900,
                  lineHeight: 0.9, letterSpacing: -3,
                  textShadow: `0 0 30px ${color}44`,
                }}>{value}</div>
                {/* Divider line */}
                {i < metrics.length - 1 && (
                  <div style={{
                    height: 1, width: lineW, marginTop: 10,
                    background: `${colorPrimary}44`,
                  }}/>
                )}
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ── HookCard — legacy (kept for backward compat) ──────────────────────────────
const HookCard = ({ text, subtext, color, theme = {} }) => {
  const T = {
    accent: "#f59e0b", bg: "#0a0a1a", surface: "rgba(10,10,26,0.92)",
    textPrimary: "#ffffff", textSecond: "#f59e0b", style: "kinetic",
    ...theme,
  };
  return (
    <FilmCard
      text={text}
      subtext={subtext}
      colorPrimary={color || T.accent}
      colorSecondary="#ffffff"
      bgGradientStart={T.bg}
      bgGradientEnd="#000000"
      typography="ultra_heavy"
      animation="slam"
      grain={0.28}
      vignette={0.5}
      textPosition={T.style === "documentary" || T.style === "broadcast" ? "left" : "center"}
    />
  );
};

// ── StatCard — legacy (kept for backward compat) ──────────────────────────────
const StatCard = ({ ticker, direction, score, pnl, theme = {} }) => {
  const T = { accent: "#f59e0b", bg: "#0a0a1a", style: "kinetic", ...theme };
  return (
    <ImpactStat
      ticker={ticker}
      direction={direction}
      score={score}
      pnl={pnl}
      colorPrimary={T.accent}
      bgGradientStart={T.bg}
      bgGradientEnd="#000000"
      grain={0.28}
      vignette={0.5}
    />
  );
};

// ── BrandBar ─────────────────────────────────────────────────────────────────
const BrandBar = ({ label = "NacArtha AI Lab", theme = {}, colorPrimary }) => {
  const accentColor = colorPrimary || (theme && theme.accent) || "#f59e0b";
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill>
      <div style={{
        position: "absolute", bottom: 0, left: 0, right: 0, height: 56,
        background: `${accentColor}e8`,
        display: "flex", alignItems: "center", justifyContent: "center", opacity,
      }}>
        <span style={{
          color: "#000000", fontWeight: 900, fontSize: 20, letterSpacing: 4,
          fontFamily: "Arial Black, sans-serif",
        }}>▶ {label.toUpperCase()}</span>
      </div>
    </AbsoluteFill>
  );
};

// ── DarkOverlay ───────────────────────────────────────────────────────────────
const DarkOverlay = ({ opacity: targetOpacity = 0.55 }) => {
  const frame = useCurrentFrame();
  const op = interpolate(frame, [0, 8], [0, targetOpacity], { extrapolateRight: "clamp" });
  return <AbsoluteFill style={{ background: `rgba(0,0,0,${op})` }} />;
};

module.exports = {
  // New cinematic compositions
  FilmCard, TypoSlam, GlitchHook, SplitReveal, WordPunch, NewsFlash,
  ImpactStat, WinLoseSlam, DataReveal,
  // Legacy
  HookCard, StatCard, CTACard,
  BrandBar, DarkOverlay,
};
