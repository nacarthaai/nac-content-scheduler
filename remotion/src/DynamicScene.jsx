/**
 * DynamicScene — AI-driven visual interpreter for Remotion
 *
 * The AI in engine_15 generates a `visual_program` JSON.
 * This component reads the layer list and renders each layer type
 * with its specific animation and styling params.
 *
 * Supported layer types:
 *   bg          — gradient or solid background
 *   grain       — film grain overlay
 *   vignette    — dark edge vignette
 *   glow_orb    — ambient light blob
 *   text_block  — animated text (word_slam | slow_fade | type_in | all_at_once)
 *   ticker_bar  — scrolling text bar (top | bottom)
 *   badge       — colored pill / label box
 *   counter     — animated counting number
 *   split_line  — glowing vertical or horizontal divider
 *   data_grid   — stacked label+value rows cascading in
 *   accent_line — thin line that grows from a point
 *   scan_bar    — moving horizontal scan sweep
 *   glow_rect   — glowing rectangle border
 *   circle_ring — expanding/pulsing circle
 */

const {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
  spring,
} = require("remotion");

// ── Helpers ────────────────────────────────────────────────────────────────────
const hex2rgba = (hex, a = 1) => {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${a})`;
};

const resolveY = (y, height) => {
  if (typeof y === "number") return y;
  if (y === "center") return height / 2;
  if (typeof y === "string" && y.startsWith("center")) {
    const offset = parseInt(y.replace("center", "")) || 0;
    return height / 2 + offset;
  }
  if (typeof y === "string" && y.startsWith("bottom-")) {
    const offset = parseInt(y.replace("bottom-", "")) || 0;
    return height - offset;
  }
  if (typeof y === "string" && y.endsWith("%")) {
    return (parseFloat(y) / 100) * height;
  }
  return height / 2;
};

const resolveX = (x, width) => {
  if (typeof x === "number") return x;
  if (x === "center") return width / 2;
  if (x === "right") return width;
  if (typeof x === "string" && x.endsWith("%")) {
    return (parseFloat(x) / 100) * width;
  }
  return x || 80;
};

// ── Layer: bg ─────────────────────────────────────────────────────────────────
const BgLayer = ({ colors = ["#0a0a1a", "#000000"], solid, angle = 165 }) => {
  const bg = solid
    ? solid
    : `linear-gradient(${angle}deg, ${colors[0]} 0%, ${colors[1] || "#000000"} 100%)`;
  return <AbsoluteFill style={{ background: bg }}/>;
};

// ── Layer: grain ──────────────────────────────────────────────────────────────
const GrainLayer = ({ opacity = 0.3 }) => (
  <AbsoluteFill style={{ mixBlendMode: "overlay", opacity, pointerEvents: "none" }}>
    <svg width="100%" height="100%" style={{ position: "absolute", top: 0, left: 0 }}>
      <defs>
        <filter id="dyn_grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" stitchTiles="stitch"/>
          <feColorMatrix type="saturate" values="0"/>
        </filter>
      </defs>
      <rect width="100%" height="100%" filter="url(#dyn_grain)"/>
    </svg>
  </AbsoluteFill>
);

// ── Layer: vignette ───────────────────────────────────────────────────────────
const VignetteLayer = ({ strength = 0.5 }) => (
  <AbsoluteFill style={{
    background: `radial-gradient(ellipse at 50% 45%, transparent 28%, rgba(0,0,0,${strength}) 100%)`,
    pointerEvents: "none",
  }}/>
);

// ── Layer: glow_orb ────────────────────────────────────────────────────────────
const GlowOrbLayer = ({ x = -60, y = "35%", size = 500, color = "#f59e0b", opacity = 0.18 }) => {
  const { width, height } = useVideoConfig();
  const cx = resolveX(x, width);
  const cy = resolveY(y, height);
  return (
    <div style={{
      position: "absolute",
      left: cx - size / 2, top: cy - size / 2,
      width: size, height: size, borderRadius: "50%",
      background: `radial-gradient(circle, ${hex2rgba(color, opacity)} 0%, transparent 70%)`,
      filter: `blur(${size * 0.12}px)`,
      pointerEvents: "none",
    }}/>
  );
};

// ── Layer: text_block ──────────────────────────────────────────────────────────
// entry: "word_slam" | "slow_fade" | "type_in" | "all_at_once" | "slide_left" | "slide_right"
const TextBlockLayer = ({
  content = "",
  x = 80,
  y = "center",
  size = 100,
  weight = 900,
  color = "#ffffff",
  last_word_color,    // accent color on last word (word_slam only)
  font = "Arial Black, Impact, sans-serif",
  transform = "uppercase",
  letter_spacing = -2,
  line_height = 0.92,
  entry = "word_slam",
  entry_frame = 0,
  stagger = 8,        // frames between words (word_slam)
  duration = 18,      // spring duration per word
  align = "left",     // left | center | right
  max_width,
  shadow,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const cx = resolveX(x, width);
  const cy = resolveY(y, height);

  const words = String(content).split(" ").filter(Boolean);

  const springCfg = { damping: 10, mass: 0.9 };
  const textShadow = shadow || `0 4px 40px rgba(0,0,0,0.5)`;
  const mw = max_width || (width - cx - 40);

  // ── all_at_once / slow_fade ──────────────────────────────────────────────────
  if (entry === "all_at_once" || entry === "slow_fade") {
    const dur   = entry === "slow_fade" ? 30 : 10;
    const op    = interpolate(frame - entry_frame, [0, dur], [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    const slide = entry === "slow_fade"
      ? interpolate(frame - entry_frame, [0, dur], [20, 0],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
      : 0;
    return (
      <div style={{
        position: "absolute", left: cx, top: cy,
        transform: `translateY(-50%) translateY(${slide}px)`,
        opacity: op,
        fontFamily: font,
        fontSize: size,
        fontWeight: weight,
        textTransform: transform,
        letterSpacing: letter_spacing,
        lineHeight: line_height,
        color,
        maxWidth: mw,
        textAlign: align,
        textShadow,
      }}>{content}</div>
    );
  }

  // ── slide_left / slide_right ─────────────────────────────────────────────────
  if (entry === "slide_left" || entry === "slide_right") {
    const dir = entry === "slide_left" ? -200 : 200;
    const p   = spring({ frame: frame - entry_frame, fps,
      from: 0, to: 1, durationInFrames: 22, config: { damping: 13 } });
    const tx  = interpolate(p, [0, 1], [dir, 0]);
    const op  = interpolate(frame - entry_frame, [0, 10], [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    return (
      <div style={{
        position: "absolute", left: cx, top: cy,
        transform: `translateY(-50%) translateX(${tx}px)`,
        opacity: op,
        fontFamily: font,
        fontSize: size,
        fontWeight: weight,
        textTransform: transform,
        letterSpacing: letter_spacing,
        lineHeight: line_height,
        color,
        maxWidth: mw,
        textAlign: align,
        textShadow,
      }}>{content}</div>
    );
  }

  // ── type_in — characters appear one by one ───────────────────────────────────
  if (entry === "type_in") {
    const chars   = String(content).split("");
    const visible = Math.floor(interpolate(frame - entry_frame, [0, chars.length * 3], [0, chars.length],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
    const shown   = chars.slice(0, visible).join("");
    const op      = interpolate(frame - entry_frame, [0, 4], [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    return (
      <div style={{
        position: "absolute", left: cx, top: cy,
        transform: "translateY(-50%)",
        opacity: op,
        fontFamily: font,
        fontSize: size,
        fontWeight: weight,
        textTransform: transform,
        letterSpacing: letter_spacing,
        lineHeight: line_height,
        color,
        maxWidth: mw,
        textShadow,
      }}>
        {shown}
        {visible < chars.length && (
          <span style={{
            opacity: frame % 10 < 5 ? 1 : 0,
            color,
          }}>▌</span>
        )}
      </div>
    );
  }

  // ── word_slam (default) ──────────────────────────────────────────────────────
  return (
    <div style={{
      position: "absolute", left: cx, top: cy,
      transform: "translateY(-50%)",
      maxWidth: mw,
      textAlign: align,
    }}>
      {words.map((word, i) => {
        const startF = entry_frame + i * stagger;
        const p = spring({ frame: frame - startF, fps,
          from: 0, to: 1, durationInFrames: duration, config: springCfg });
        const ty  = interpolate(p, [0, 1], [80, 0]);
        const op  = interpolate(frame - startF, [0, 7], [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const isLast   = i === words.length - 1;
        const wordColor = (isLast && last_word_color) ? last_word_color : color;
        return (
          <span key={i} style={{ display: "inline-block", marginRight: size * 0.12 }}>
            <span style={{
              display: "block",
              transform: `translateY(${ty}px)`,
              opacity: op,
              fontFamily: font,
              fontSize: size,
              fontWeight: weight,
              textTransform: transform,
              letterSpacing: letter_spacing,
              lineHeight: line_height,
              color: wordColor,
              textShadow,
            }}>{word}</span>
          </span>
        );
      })}
    </div>
  );
};

// ── Layer: ticker_bar ──────────────────────────────────────────────────────────
const TickerBarLayer = ({
  position = "top",       // top | bottom
  content = "NACARTHA AI · LIVE SIGNAL",
  color = "#ef4444",
  text_color = "#ffffff",
  height: barH = 52,
  font_size = 22,
  entry_frame = 0,
  scroll_speed = 1,       // px per frame
  label,                  // bold prefix badge ("BREAKING")
}) => {
  const frame = useCurrentFrame();
  const { width } = useVideoConfig();
  const scrollX = -(frame - entry_frame) * scroll_speed * 2;
  const slideIn = interpolate(frame - entry_frame, [0, 18],
    [position === "top" ? -barH : barH, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const repeated = (content + " · ").repeat(6);
  return (
    <div style={{
      position: "absolute",
      [position]: 0,
      left: 0, right: 0,
      height: barH,
      transform: `translateY(${slideIn}px)`,
      display: "flex", alignItems: "stretch", overflow: "hidden",
    }}>
      {label && (
        <div style={{
          background: color, color: text_color,
          fontFamily: "Arial Black, sans-serif",
          fontSize: font_size * 0.9, fontWeight: 900, letterSpacing: 4,
          padding: "0 24px", display: "flex", alignItems: "center",
          flexShrink: 0,
        }}>{label}</div>
      )}
      <div style={{
        flex: 1, background: label ? "rgba(255,255,255,0.07)" : color,
        borderTop: `2px solid ${color}`,
        borderBottom: `2px solid ${color}`,
        overflow: "hidden",
        display: "flex", alignItems: "center",
      }}>
        <div style={{
          color: label ? text_color : "#000000",
          fontFamily: "Arial Black, sans-serif",
          fontSize: font_size, fontWeight: label ? 600 : 900,
          letterSpacing: 3, whiteSpace: "nowrap",
          transform: `translateX(${scrollX}px)`,
        }}>{repeated}</div>
      </div>
    </div>
  );
};

// ── Layer: badge ───────────────────────────────────────────────────────────────
const BadgeLayer = ({
  content = "SHORT",
  x = 80, y = "center",
  bg_color = "#ef4444",
  text_color = "#ffffff",
  font_size = 28,
  padding_x = 28, padding_y = 10,
  entry_frame = 0,
  entry = "slide_left",
  letter_spacing = 4,
  glow = true,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const cx = resolveX(x, width);
  const cy = resolveY(y, height);
  const p = spring({ frame: frame - entry_frame, fps,
    from: 0, to: 1, durationInFrames: 20, config: { damping: 11 } });
  const tx = entry === "slide_left" ? interpolate(p, [0, 1], [-400, 0]) : 0;
  const sc = entry === "scale" ? interpolate(p, [0, 1], [0, 1]) : 1;
  const op = interpolate(frame - entry_frame, [0, 8], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{
      position: "absolute", left: cx, top: cy,
      transform: `translateY(-50%) translateX(${tx}px) scale(${sc})`,
      opacity: op,
      background: bg_color,
      color: text_color,
      fontFamily: "Arial Black, sans-serif",
      fontSize: font_size, fontWeight: 900,
      letterSpacing: letter_spacing,
      padding: `${padding_y}px ${padding_x}px`,
      boxShadow: glow ? `0 0 30px ${hex2rgba(bg_color, 0.7)}` : "none",
      whiteSpace: "nowrap",
    }}>{content}</div>
  );
};

// ── Layer: counter ─────────────────────────────────────────────────────────────
const CounterLayer = ({
  label = "",
  target = 50,
  prefix = "$",
  suffix = "",
  color = "#ef4444",
  x = 80, y = "center",
  size = 140,
  weight = 900,
  entry_frame = 0,
  count_frames = 60,
  slam_frame,     // frame at which counter stops and slams to final value
  letter_spacing = -6,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const cx = resolveX(x, width);
  const cy = resolveY(y, height);

  const prog  = interpolate(frame - entry_frame, [0, count_frames], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const shown = Math.round(prog * Math.abs(target));
  const sign  = target < 0 ? "-" : target > 0 && prefix === "$" ? "+" : "";

  const slamF = slam_frame || (entry_frame + count_frames);
  const slamScale = spring({ frame: frame - slamF, fps,
    from: 1.4, to: 1, durationInFrames: 12, config: { damping: 7 } });
  const scale = frame >= slamF ? slamScale : 1;
  const op    = interpolate(frame - entry_frame, [0, 6], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <div style={{
      position: "absolute", left: cx, top: cy,
      transform: `translateY(-50%) scale(${scale})`,
      transformOrigin: "left center",
      opacity: op,
    }}>
      {label && (
        <div style={{
          color: "rgba(255,255,255,0.4)", fontSize: size * 0.17,
          letterSpacing: 5, marginBottom: 8, fontWeight: 400,
        }}>{label}</div>
      )}
      <div style={{
        fontFamily: "Arial Black, Impact, sans-serif",
        fontSize: size, fontWeight: weight,
        color, letterSpacing: letter_spacing, lineHeight: 0.85,
        textShadow: `0 0 80px ${hex2rgba(color, 0.5)}`,
      }}>{sign}{prefix}{shown}{suffix}</div>
    </div>
  );
};

// ── Layer: split_line ──────────────────────────────────────────────────────────
const SplitLineLayer = ({
  orientation = "vertical",  // vertical | horizontal
  position = "50%",           // % or px
  color = "#ef4444",
  thickness = 3,
  glow = true,
  entry_frame = 0,
  entry = "sweep",           // sweep | fade
}) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const op    = interpolate(frame - entry_frame, [0, 14], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const pct   = typeof position === "string" && position.endsWith("%")
    ? parseFloat(position) / 100 : parseFloat(position) / (orientation === "vertical" ? width : height);
  const px    = pct * (orientation === "vertical" ? width : height);

  if (orientation === "vertical") {
    const h = entry === "sweep"
      ? interpolate(frame - entry_frame, [0, 25], [0, height],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
      : height;
    return (
      <div style={{
        position: "absolute", left: px - thickness / 2, top: 0,
        width: thickness, height: h,
        background: `linear-gradient(180deg, transparent, ${color}, transparent)`,
        boxShadow: glow ? `0 0 30px ${color}, 0 0 60px ${hex2rgba(color, 0.3)}` : "none",
        opacity: op,
      }}/>
    );
  }
  const w = entry === "sweep"
    ? interpolate(frame - entry_frame, [0, 25], [0, width],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
    : width;
  return (
    <div style={{
      position: "absolute", top: px - thickness / 2, left: 0,
      height: thickness, width: w,
      background: `linear-gradient(90deg, transparent, ${color}, transparent)`,
      boxShadow: glow ? `0 0 20px ${color}` : "none",
      opacity: op,
    }}/>
  );
};

// ── Layer: data_grid ───────────────────────────────────────────────────────────
const DataGridLayer = ({
  rows = [],   // [{label, value, color}]
  x = 100, y = "center",
  label_size = 16,
  value_size = 72,
  value_weight = 900,
  stagger = 16,
  entry_frame = 0,
  show_dividers = true,
  accent_bar_color,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const cx = resolveX(x, width);
  const cy = resolveY(y, height);
  const totalH = rows.length * (value_size + label_size + 24 + 10);

  return (
    <div style={{
      position: "absolute", left: cx, top: cy,
      transform: `translateY(-${totalH / 2}px)`,
    }}>
      {/* Accent bar on left */}
      {accent_bar_color && (
        <div style={{
          position: "absolute", left: -20, top: 0, bottom: 0, width: 4,
          background: `linear-gradient(180deg, transparent, ${accent_bar_color}, transparent)`,
          boxShadow: `0 0 14px ${accent_bar_color}`,
          opacity: interpolate(frame - entry_frame, [0, 20], [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
        }}/>
      )}
      {rows.map(({ label = "", value = "", color = "#ffffff" }, i) => {
        const startF = entry_frame + i * stagger;
        const tx = interpolate(frame - startF, [0, 18], [-120, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const op = interpolate(frame - startF, [0, 10], [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const lineW = interpolate(frame - startF, [12, 32], [0, width - cx * 2 - 40],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return (
          <div key={i} style={{
            transform: `translateX(${tx}px)`, opacity: op, marginBottom: 20,
          }}>
            <div style={{
              color: "rgba(255,255,255,0.35)", fontSize: label_size,
              letterSpacing: 5, fontWeight: 400, marginBottom: 4,
            }}>{label}</div>
            <div style={{
              fontFamily: "Arial Black, Impact, sans-serif",
              fontSize: value_size, fontWeight: value_weight,
              color, lineHeight: 0.9, letterSpacing: -3,
              textShadow: `0 0 30px ${hex2rgba(color, 0.35)}`,
            }}>{value}</div>
            {show_dividers && i < rows.length - 1 && (
              <div style={{ height: 1, width: lineW, marginTop: 12,
                background: "rgba(255,255,255,0.12)" }}/>
            )}
          </div>
        );
      })}
    </div>
  );
};

// ── Layer: accent_line ─────────────────────────────────────────────────────────
const AccentLineLayer = ({
  x = 80, y = "bottom-90",
  length = 240,
  color = "#f59e0b",
  thickness = 3,
  direction = "right",   // right | left | center
  glow = true,
  entry_frame = 0,
  grow_frames = [0, 30],
}) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const cx = resolveX(x, width);
  const cy = resolveY(y, height);
  const w  = interpolate(frame, grow_frames, [0, length],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const left = direction === "center" ? cx - w / 2 : direction === "left" ? cx - w : cx;
  return (
    <div style={{
      position: "absolute", left, top: cy, height: thickness, width: w,
      background: `linear-gradient(90deg, ${direction === "right" ? "" : "transparent,"}${color}${direction === "right" ? ",transparent" : ""})`,
      boxShadow: glow ? `0 0 16px ${hex2rgba(color, 0.8)}` : "none",
    }}/>
  );
};

// ── Layer: scan_bar ───────────────────────────────────────────────────────────
const ScanBarLayer = ({ color = "#00e5ff", speed = 0.5, opacity = 0.06, entry_frame = 0 }) => {
  const frame = useCurrentFrame();
  const { height } = useVideoConfig();
  if (frame < entry_frame) return null;
  const y = ((frame - entry_frame) * speed * 6) % (height + 40) - 20;
  return (
    <div style={{
      position: "absolute", left: 0, right: 0, top: y, height: 2,
      background: `linear-gradient(90deg, transparent, ${color}, transparent)`,
      opacity, pointerEvents: "none",
    }}/>
  );
};

// ── Layer: glow_rect ──────────────────────────────────────────────────────────
const GlowRectLayer = ({
  x = 60, y = "center",
  width: w = 900, height: h = 200,
  color = "#f59e0b",
  border = 2,
  opacity = 0.6,
  entry_frame = 0,
}) => {
  const frame = useCurrentFrame();
  const { width: vw, height: vh } = useVideoConfig();
  const cx = resolveX(x, vw);
  const cy = resolveY(y, vh);
  const op = interpolate(frame - entry_frame, [0, 14], [0, opacity],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{
      position: "absolute", left: cx, top: cy - h / 2,
      width: w, height: h,
      border: `${border}px solid ${color}`,
      boxShadow: `0 0 30px ${hex2rgba(color, 0.4)}, inset 0 0 30px ${hex2rgba(color, 0.05)}`,
      opacity: op,
    }}/>
  );
};

// ── Layer: circle_ring ────────────────────────────────────────────────────────
const CircleRingLayer = ({
  x = "50%", y = "center",
  size = 400,
  color = "#ef4444",
  opacity = 0.3,
  pulse = false,
  entry_frame = 0,
  expand_frames,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const cx = resolveX(x, width);
  const cy = resolveY(y, height);
  const baseOp = interpolate(frame - entry_frame, [0, 16], [0, opacity],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const pulseFactor = pulse ? interpolate(frame % 40, [0, 20, 40], [1, 1.05, 1]) : 1;
  const expandScale = expand_frames
    ? interpolate(frame - entry_frame, [0, expand_frames], [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
    : 1;
  const expandOpacity = expand_frames
    ? interpolate(frame - entry_frame, [0, expand_frames], [opacity, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
    : baseOp;
  const s = size * pulseFactor * expandScale;
  return (
    <div style={{
      position: "absolute",
      left: cx - s / 2, top: cy - s / 2,
      width: s, height: s, borderRadius: "50%",
      border: `2px solid ${color}`,
      opacity: expandOpacity,
      boxShadow: `0 0 20px ${hex2rgba(color, 0.5)}`,
    }}/>
  );
};

// ── RENDERER ──────────────────────────────────────────────────────────────────
const renderLayer = (layer, idx) => {
  if (!layer || !layer.type) return null;
  switch (layer.type) {
    case "bg":           return <BgLayer         key={idx} {...layer}/>;
    case "grain":        return <GrainLayer       key={idx} {...layer}/>;
    case "vignette":     return <VignetteLayer    key={idx} {...layer}/>;
    case "glow_orb":     return <GlowOrbLayer     key={idx} {...layer}/>;
    case "text_block":   return <TextBlockLayer   key={idx} {...layer}/>;
    case "ticker_bar":   return <TickerBarLayer   key={idx} {...layer}/>;
    case "badge":        return <BadgeLayer        key={idx} {...layer}/>;
    case "counter":      return <CounterLayer      key={idx} {...layer}/>;
    case "split_line":   return <SplitLineLayer    key={idx} {...layer}/>;
    case "data_grid":    return <DataGridLayer     key={idx} {...layer}/>;
    case "accent_line":  return <AccentLineLayer   key={idx} {...layer}/>;
    case "scan_bar":     return <ScanBarLayer      key={idx} {...layer}/>;
    case "glow_rect":    return <GlowRectLayer     key={idx} {...layer}/>;
    case "circle_ring":  return <CircleRingLayer   key={idx} {...layer}/>;
    default:             return null;
  }
};

// ── DynamicScene — main export ────────────────────────────────────────────────
const DynamicScene = ({ program = {} }) => {
  const layers = program.layers || [];
  return (
    <AbsoluteFill style={{ fontFamily: "Arial, sans-serif" }}>
      {layers.map((layer, i) => renderLayer(layer, i))}
    </AbsoluteFill>
  );
};

module.exports = { DynamicScene };
