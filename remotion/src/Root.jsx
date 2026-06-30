const { Composition, AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig, spring, staticFile } = require("remotion");
const {
  FilmCard, TypoSlam, GlitchHook, SplitReveal, WordPunch, NewsFlash,
  ImpactStat, WinLoseSlam, DataReveal,
  HookCard, StatCard, CTACard, BrandBar, DarkOverlay,
} = require("./KineticText");
const { DynamicScene } = require("./DynamicScene");
const { TradingChart } = require("./TradingChart");
const { AnimatedCaption } = require("./AnimatedCaption");
const { ScanLine, DigitalGrid } = require("./HUD");

// ── Default visual spec (fallback when no AI spec is provided) ───────────────
const DEFAULT_VIS = {
  colorPrimary:    "#f59e0b",
  colorSecondary:  "#ffffff",
  bgGradientStart: "#0a0a1a",
  bgGradientEnd:   "#000000",
  typography:      "ultra_heavy",
  animation:       "slam",
  grain:           0.3,
  vignette:        0.5,
  textPosition:    "left",
  layout:          "cinematic_overlay",
};

// ── Compositions ──────────────────────────────────────────────────────────────

// FilmCard — cinematic hook (primary hook composition)
const FilmCardComp = (props) => (
  <FilmCard {...{ ...DEFAULT_VIS, ...props }} />
);

// TypoSlam — word-by-word slam (for typo_slam layout)
const TypoSlamComp = (props) => (
  <TypoSlam {...{ ...DEFAULT_VIS, ...props }} />
);

// SplitCard — vertical split reveal
const SplitCardComp  = (props) => <SplitReveal {...{ ...DEFAULT_VIS, ...props }}/>;
// DataBurst — cascading data reveal
const DataBurstComp  = (props) => <DataReveal  {...{ ...DEFAULT_VIS, ...props }}/>;
// GlitchHook — chromatic aberration glitch
const GlitchHookComp = (props) => <GlitchHook {...{ ...DEFAULT_VIS, ...props }}/>;
// WordPunch — single word slam then supporting text
const WordPunchComp  = (props) => <WordPunch  {...{ ...DEFAULT_VIS, ...props }}/>;
// NewsFlash — breaking news bar
const NewsFlashComp  = (props) => <NewsFlash  {...{ ...DEFAULT_VIS, ...props }}/>;
// ImpactStat — P&L counter
const ImpactStatComp = (props) => <ImpactStat {...{ ...DEFAULT_VIS, ...props }}/>;
// WinLoseSlam — WIN/LOSS fullscreen slam then stats
const WinLoseSlamComp = (props) => <WinLoseSlam {...{ ...DEFAULT_VIS, ...props }}/>;

// CTACard composition
const CTAComposition = (props) => (
  <CTACard {...{ ...DEFAULT_VIS, ...props }} />
);

// TradingChart — passes all visual props through
const TradingChartComposition = (props) => <TradingChart {...props}/>;

// AnimatedCaption
const CaptionComposition = ({ words }) => (
  <AbsoluteFill style={{ background: "transparent" }}>
    <AnimatedCaption words={words}/>
  </AbsoluteFill>
);

// ── Legacy wrappers (kept for backward compatibility) ─────────────────────────
const HookComposition = ({ text, subtext, color, theme }) => (
  <HookCard text={text} subtext={subtext} color={color} theme={theme}/>
);

const StatComposition = ({ ticker, direction, score, pnl, theme }) => (
  <StatCard ticker={ticker} direction={direction} score={score} pnl={pnl} theme={theme}/>
);

// ── Outro ─────────────────────────────────────────────────────────────────────
const OutroComposition = ({ logoPath, handle = "@nacartha", colorPrimary, theme = {} }) => {
  const accentColor = colorPrimary || (theme && theme.accent) || "#f59e0b";
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scale  = spring({ frame, fps, from: 0.8, to: 1, durationInFrames: 22, config: { damping: 11 } });
  const fadeIn = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: "clamp" });
  const ring   = interpolate(frame % 40, [0, 20, 40], [1, 1.06, 1]);
  const textOp = interpolate(frame, [18, 30], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{
      background: "linear-gradient(165deg, #060608 0%, #000000 100%)",
      justifyContent: "center", alignItems: "center",
    }}>
      {/* Radial glow */}
      <div style={{
        position: "absolute", width: 800, height: 800, borderRadius: "50%",
        background: `radial-gradient(circle, ${accentColor}22 0%, transparent 70%)`,
        transform: `scale(${ring})`, opacity: fadeIn,
        filter: "blur(20px)",
      }}/>

      {/* Logo */}
      <div style={{ transform: `scale(${scale})`, opacity: fadeIn, textAlign: "center" }}>
        <Img
          src={staticFile("nac_logo.png")}
          style={{ width: 360, height: 360, objectFit: "contain", display: "block", margin: "0 auto 20px" }}
        />
      </div>

      {/* Follow strip */}
      <div style={{ position: "absolute", bottom: 100, left: 0, right: 0, textAlign: "center", opacity: textOp }}>
        <div style={{ color: "#ffffff", fontSize: 28, fontWeight: 400, letterSpacing: 2 }}>
          Follow for daily AI trades
        </div>
        <div style={{
          color: accentColor, fontSize: 52, fontWeight: 900, marginTop: 10,
          fontFamily: "Arial Black, sans-serif",
          letterSpacing: 2, textShadow: `0 0 30px ${accentColor}88`,
        }}>{handle}</div>
      </div>
    </AbsoluteFill>
  );
};

// ── Registry ──────────────────────────────────────────────────────────────────
const DEFAULT_THEME = { accent: "#f59e0b", bg: "#0a0a1a", surface: "rgba(10,10,26,0.92)",
  textPrimary: "#ffffff", textSecond: "#f59e0b", style: "kinetic" };

const RemotionRoot = () => (
  <>
    {/* ── New cinematic compositions (driven by engine_15 remotion_spec) ── */}
    {/* ── HOOK compositions (6 distinct structures) ── */}
    <Composition id="FilmCard" component={FilmCardComp}
      durationInFrames={90} fps={30} width={1080} height={1920}
      defaultProps={{ ...DEFAULT_VIS, text: "THE AI KNEW", subtext: "Before the market moved", fontSize: 100 }}
    />
    <Composition id="TypoSlam" component={TypoSlamComp}
      durationInFrames={90} fps={30} width={1080} height={1920}
      defaultProps={{ ...DEFAULT_VIS, text: "THE AI KNEW", subtext: "", fontSize: 110,
        colorPrimary: "#ef4444", bgGradientStart: "#0d0000" }}
    />
    <Composition id="GlitchHook" component={GlitchHookComp}
      durationInFrames={90} fps={30} width={1080} height={1920}
      defaultProps={{ ...DEFAULT_VIS, text: "SYSTEM BREACH", subtext: "AI signal detected",
        colorPrimary: "#a855f7", bgGradientStart: "#04040c" }}
    />
    <Composition id="SplitReveal" component={SplitCardComp}
      durationInFrames={90} fps={30} width={1080} height={1920}
      defaultProps={{ ...DEFAULT_VIS, text: "THE AI KNEW", subtext: "", ticker: "TSLA", direction: "SHORT",
        colorPrimary: "#ef4444", bgGradientStart: "#0a0000" }}
    />
    <Composition id="WordPunch" component={WordPunchComp}
      durationInFrames={90} fps={30} width={1080} height={1920}
      defaultProps={{ ...DEFAULT_VIS, text: "WRONG PLAY COST ME", subtext: "",
        colorPrimary: "#f59e0b", bgGradientStart: "#080400" }}
    />
    <Composition id="NewsFlash" component={NewsFlashComp}
      durationInFrames={90} fps={30} width={1080} height={1920}
      defaultProps={{ ...DEFAULT_VIS, text: "AI SIGNALS SHORT", subtext: "TSLA reversal detected",
        ticker: "TSLA", direction: "SHORT",
        colorPrimary: "#ef4444", bgGradientStart: "#070002" }}
    />

    {/* ── STAT compositions (3 distinct structures) ── */}
    <Composition id="ImpactStat" component={ImpactStatComp}
      durationInFrames={180} fps={30} width={1080} height={1920}
      defaultProps={{ ...DEFAULT_VIS, ticker: "TSLA", direction: "SHORT", score: 65, pnl: -50 }}
    />
    <Composition id="WinLoseSlam" component={WinLoseSlamComp}
      durationInFrames={180} fps={30} width={1080} height={1920}
      defaultProps={{ ...DEFAULT_VIS, ticker: "TSLA", direction: "SHORT", score: 65, pnl: -50,
        colorPrimary: "#ef4444", bgGradientStart: "#1a0000" }}
    />
    <Composition id="DataReveal" component={DataBurstComp}
      durationInFrames={180} fps={30} width={1080} height={1920}
      defaultProps={{ ...DEFAULT_VIS, ticker: "TSLA", direction: "SHORT", score: 65, pnl: -50,
        colorPrimary: "#00e5ff", bgGradientStart: "#020610" }}
    />

    {/* ── Trading Chart ── */}
    <Composition id="TradingChart" component={TradingChartComposition}
      durationInFrames={1050} fps={30} width={1080} height={1920}
      defaultProps={{
        ticker: "TSLA", direction: "SHORT", pnl: -50, score: 65,
        strategy: "intraday", entryIdx: 20, exitIdx: 27,
        support: 0, resistance: 0, candles: [], rsi: [],
        hudColor: "#f59e0b", bgGradientStart: "#0a0a1a", bgGradientEnd: "#000000",
        grain: 0.3, vignette: 0.5,
      }}
    />

    {/* ── CTA ── */}
    <Composition id="CTACard" component={CTAComposition}
      durationInFrames={150} fps={30} width={1080} height={1920}
      defaultProps={{ ...DEFAULT_VIS, handle: "@nacartha" }}
    />

    {/* ── DynamicScene — AI-generated visual program ── */}
    <Composition id="DynamicScene" component={({ program }) => <DynamicScene program={program}/>}
      durationInFrames={90} fps={30} width={1080} height={1920}
      defaultProps={{ program: { layers: [
        { type: "bg", colors: ["#0a0a1a", "#000000"] },
        { type: "grain", opacity: 0.3 },
        { type: "vignette", strength: 0.5 },
        { type: "text_block", content: "THE AI KNEW", x: 80, y: "center", size: 100,
          color: "#ffffff", last_word_color: "#f59e0b", entry: "word_slam" },
      ]} }}
    />
    <Composition id="DynamicStat" component={({ program }) => <DynamicScene program={program}/>}
      durationInFrames={180} fps={30} width={1080} height={1920}
      defaultProps={{ program: { layers: [
        { type: "bg", colors: ["#1a0000", "#000000"] },
        { type: "grain", opacity: 0.3 },
        { type: "vignette", strength: 0.5 },
        { type: "counter", label: "REALIZED P&L", target: -50, prefix: "$", color: "#ef4444",
          x: 80, y: "center", size: 140, entry_frame: 0, count_frames: 60 },
      ]} }}
    />

    {/* ── Caption ── */}
    <Composition id="AnimatedCaption" component={CaptionComposition}
      durationInFrames={1650} fps={30} width={1080} height={1920}
      defaultProps={{ words: [] }}
    />

    {/* ── Outro ── */}
    <Composition id="Outro" component={OutroComposition}
      durationInFrames={180} fps={30} width={1080} height={1920}
      defaultProps={{ logoPath: null, handle: "@nacartha", colorPrimary: "#f59e0b" }}
    />

    {/* ── Legacy (backward compat) ── */}
    <Composition id="HookCard" component={HookComposition}
      durationInFrames={90} fps={30} width={1080} height={1920}
      defaultProps={{ text: "WHY DID WE SHORT TSLA?", subtext: "Our AI knew before the market",
        color: "#f59e0b", theme: DEFAULT_THEME }}
    />
    <Composition id="StatCard" component={StatComposition}
      durationInFrames={180} fps={30} width={1080} height={1920}
      defaultProps={{ ticker: "TSLA", direction: "SHORT", score: 65, pnl: -50, theme: DEFAULT_THEME }}
    />
  </>
);

module.exports = { RemotionRoot };
